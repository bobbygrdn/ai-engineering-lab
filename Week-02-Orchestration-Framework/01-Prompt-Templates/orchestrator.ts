import "dotenv/config";
import { z } from "zod";
import { ChatOpenAI, OpenAIEmbeddings } from "@langchain/openai";
import { cosineSimilarity } from "@langchain/core/utils/math";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { RunnableLambda } from "@langchain/core/runnables";

// 1. THE CONTRACT (Zod)
const ActionItemSchema = z.object({
    task: z.string().describe("The specific action to be taken."),
    assignee: z.string().optional().default("Unassigned"),
    priority: z.enum(["High", "Medium", "Low"]).default("Medium"),
});

const AnalysisSchema = z.object({
    summary: z.string().describe("A 2-sentence overview of the text."),
    action_items: z.array(ActionItemSchema).default([]),
});

type MeetingAnalysis = z.infer<typeof AnalysisSchema>;

// 2. THE MODEL
const model = new ChatOpenAI({ 
    modelName: "gpt-4o", 
    temperature: 0,
});

const structuredModel = model.withStructuredOutput(AnalysisSchema);

// 3. THE PROMPT
const prompt = ChatPromptTemplate.fromTemplate(
    "You are an Elite Project Engineer. Analyze the following text and extract action items as a concise, verb-first list. Standardize terminology (e.g., use 'Fix' instead of 'Resolve').\n\nText: {input}"
);

// 4. THE DEDUPER (RunnableLambda)
const embeddings = new OpenAIEmbeddings();

const deduper = new RunnableLambda({
    func: async (results: MeetingAnalysis[]) => {
        const allActions = results.flatMap(r => r.action_items);
        if (allActions.length === 0) return { summary: "", action_items: [] };

        // 1. Generate embeddings for all tasks at once
        const taskVectors = await embeddings.embedDocuments(
            allActions.map(a => a.task.toLowerCase())
        );

        const uniqueActions: z.infer<typeof ActionItemSchema>[] = [];
        const seenIndices = new Set<number>();

        for (let i = 0; i < allActions.length; i++) {
            if (seenIndices.has(i)) continue;

            uniqueActions.push(allActions[i]);

            for (let j = i + 1; j < allActions.length; j++) {
                // 2. Compare the conceptual similarity of vectors
                const similarity = cosineSimilarity([taskVectors[i]], [taskVectors[j]])[0][0];

                // 3. Concepts that are >82% similar are treated as duplicates
                if (similarity > 0.82) {
                    seenIndices.add(j);
                }
            }
        }

        const rawSummaries = results.map(r => r.summary.trim());
        const summaryVectors = await embeddings.embedDocuments(rawSummaries);
        
        const uniqueSummaries: string[] = [];
        const seenSummaryIndices = new Set<number>();

        for (let i = 0; i < rawSummaries.length; i++) {
            if (seenSummaryIndices.has(i)) continue;
            uniqueSummaries.push(rawSummaries[i]);

            for (let j = i + 1; j < rawSummaries.length; j++) {
                const sim = cosineSimilarity([summaryVectors[i]], [summaryVectors[j]])[0][0];
                // If the summaries are >85% similar, they are redundant
                if (sim > 0.85) {
                    seenSummaryIndices.add(j);
                }
            }
        }

        const finalSummary = uniqueSummaries.join(" ");

        return { summary: finalSummary, action_items: uniqueActions };
    }
});

// 5. THE CLEAN LCEL PIPE
const extractionChain = prompt.pipe(structuredModel);

// 6. THE ORCHESTRATOR
const fullOrchestrator = RunnableLambda.from(async (inputs: { input: string }[]) => {
    const results = await extractionChain.batch(inputs);
    return deduper.invoke(results as MeetingAnalysis[]);
});

// 7. EXECUTION
async function run() {
    const chunks = [
        "Meeting start: Robert needs to fix the API bug by Friday. Overall, the project is on track.",
        "Closing notes: Robert must resolve the issue with the API endpoint by the end of the week."
    ];

    console.log("Running Professional Orchestrator...");
    try {
        const finalOutput = await fullOrchestrator.invoke(chunks.map(c => ({ input: c })));
        console.dir(finalOutput, { depth: null });
    } catch (error) {
        console.error("Orchestration failed:", error);
    }
}

run();