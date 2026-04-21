import { SecretsManagerClient, GetSecretValueCommand } from "@aws-sdk/client-secrets-manager";
import { ChatOpenAI } from "@langchain/openai";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { z } from "zod";

const secretsClient = new SecretsManagerClient({ region: "us-east-1" });
let cachedChain: any = null;

const responseSchema = z.object({
    summary: z.string().describe("A brief summary of the project and the tasks that need to be completed."),
    tasks: z.array(z.object({
        name: z.string().describe("The name of the task."),
        category: z.string().describe("The category of the task."),
        assigned_to: z.string().nullable().describe("The name of the person that is responsible for the task."),
        urgency: z.enum(["low", "medium", "high"]).describe("The urgency of the task.")
    }))
});

async function getChain() {
    if (cachedChain) return cachedChain;

    const secretResponse = await secretsClient.send(
        new GetSecretValueCommand({ SecretId: "dev/openai/ai-engineering-lab" })
    )
    const secrets = JSON.parse(secretResponse.SecretString || "{}");
    const key = secrets.OPENAI_API_KEY;

    if (!key) {
        throw new Error("OPENAI_API_KEY not found in Secrets Manager response.");
    }

    const model = new ChatOpenAI({
        apiKey: key,
        modelName: "gpt-4o",
        temperature: 0
    }).withStructuredOutput(responseSchema);

    const prompt = ChatPromptTemplate.fromMessages([
        ["system", "You are a helpful assistant that helps to break down complex projects into smaller, manageable tasks. You will be given a project description and you need to generate a list of tasks that need to be completed to accomplish the project. Each task should have a name, category, assigned to (if applicable), and urgency level. Only use information explicitly stated in the project description to generate tasks. If the project description does not specify who should be assigned to a task, set the assigned to as null. The urgency level should be determined based on the information provided in the project description. If there is no information about urgency, default to medium."],
        ["human", "Plan a quick coffee meet-up."],
        ["ai", "{{\"summary\": \"To plan a quick coffee meet-up, we need to identify the tasks involved in organizing the event.\", \"tasks\": [{{\"name\": \"Choose a date and time\", \"category\": \"Scheduling\", \"assigned_to\": null, \"urgency\": \"high\"}}]}}"],
        ["human", "{project_description}"],
    ]);

    cachedChain = prompt.pipe(model);
    return cachedChain;
};

export const handler = async (event: any) => {
    console.log("EVENT RECEIVED:", JSON.stringify(event));
    try {
        const body = event.body ? JSON.parse(event.body) : {};
        const { project_description } = body;

        if (!project_description) {
            return {
                statusCode: 400,
                body: JSON.stringify({error: "Please provide a project description."})
            };
        }

        const chain = await getChain();

        const result = await chain.invoke({ project_description });

        return {
            statusCode: 200,
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(result),
        };
    } catch (error: any) {
        console.error("LAMBDA ERROR:", error);
        return {
            statusCode: 500,
            body: JSON.stringify({error: "Internal Server Error", message: error.message, stack: error.stack}),
        };
    }
};