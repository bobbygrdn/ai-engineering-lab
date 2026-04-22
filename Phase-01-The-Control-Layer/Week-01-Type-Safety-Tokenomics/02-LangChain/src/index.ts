import { ChatOpenAI } from "@langchain/openai";
import dotenv from "dotenv";
import { ChatPromptTemplate } from "@langchain/core/prompts";
import { z } from "zod";

dotenv.config();

const apiKey = process.env.OPENAI_API_KEY;

const model = new ChatOpenAI({
    model: "gpt-4o-mini",
    temperature: 0,
    openAIApiKey: apiKey,
});

const taskSchema = z.object({
    name: z.string().describe("The name of the task."),
    category: z.string().describe("The category of the task."),
    assigned_to: z.string().nullable().describe("The name of the person that is responsible for the task."),
    urgency: z.enum(["low", "medium", "high"]).describe("The urgency of the task.")
});

const tasksSchema = z.array(taskSchema).describe("A list of tasks to be completed.");

const responseSchema = z.object({
    tasks: tasksSchema,
    summary: z.string().describe("A brief summary of the tasks.")
});

const modelWithStructure = model.withStructuredOutput(responseSchema);

const prompt = ChatPromptTemplate.fromMessages([
    ["system", "You are a helpful assistant that helps to break down complex projects into smaller, manageable tasks. You will be given a project description and you need to generate a list of tasks that need to be completed to accomplish the project. Each task should have a name, category, assigned to (if applicable), and urgency level. Only use information explicitly stated in the project description to generate tasks. If the project description does not specify who should be assigned to a task, set the assigned to as null. The urgency level should be determined based on the information provided in the project description. If there is no information about urgency, default to medium."],
    ["human", "Plan a quick coffee meet-up."],
    ["ai", "{{\"summary\": \"To plan a quick coffee meet-up, we need to identify the tasks involved in organizing the event.\", \"tasks\": [{{\"name\": \"Choose a date and time\", \"category\": \"Scheduling\", \"assigned_to\": null, \"urgency\": \"high\"}}]}}"],
    ["human", "{project_description}"],
]);

// const formattedPrompt = await prompt.formatMessages({
//     project_description: "Plan a birthday party for my friend. The party should include a venue, catering, entertainment, and invitations."
// });

// console.log(formattedPrompt);

const chain = prompt.pipe(modelWithStructure);

const result = await chain.invoke({
    project_description: "Plan a birthday party for my friend. The party should include a venue, catering, entertainment, and invitations."
});

console.log(result.summary);
console.table(result.tasks);