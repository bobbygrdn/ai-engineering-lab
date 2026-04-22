import { SecretsManagerClient, GetSecretValueCommand } from "@aws-sdk/client-secrets-manager";
import { CheerioWebBaseLoader } from "@langchain/community/document_loaders/web/cheerio";
import { ChatOpenAI } from "@langchain/openai";
import { z } from "zod";

const TechStackSchema = z.object({
    postings: z.array(z.object({
        company: z.string().describe("The name of the company hiring"),
        role: z.string().describe("The job title"),
        tech_stack: z.array(z.string()).describe("List of technologies mentioned"),
        evidence: z.string().describe("The EXACT sentence or phrase from the text that proves this tech stack is required.")
    }))
});

const secretsClient = new SecretsManagerClient({ region: "us-east-1" });

const secretResponse = await secretsClient.send(
    new GetSecretValueCommand({ SecretId: "dev/openai/ai-engineering-lab"})
);
const secrets = JSON.parse(secretResponse.SecretString || "{}");
const key = secrets.OPENAI_API_KEY;

export const handler = async (event:any) => {
    if (!event.body) {
        return {
            statusCode: 400,
            body: JSON.stringify({ error: "Missing request body" }),
        }
    }

    const body = typeof event.body === "string" ? JSON.parse(event.body) : event.body;
    const { targetUrl } = body;

    if (!targetUrl) {
        return {
            statusCode: 400,
            body: JSON.stringify({ error: "Missing 'targetUrl' in request body" }),
        }
    }
    try {
        const loader = new CheerioWebBaseLoader("https://jobs.sevendaysvt.com/tech-jobs-vermont/");
        const docs = await loader.load();
        const rawText = docs.map(d => d.pageContent).join("\n\n");

        const model = new ChatOpenAI({
            modelName: "gpt-4o-mini",
            temperature: 0,
            apiKey: key
        }).withStructuredOutput(TechStackSchema);

        const result = await model.invoke(`
            Extract technical job postings from the following text.
            Verify every tech_stack with a verbatim quote in the 'evidence' field.

            DATA:
            ${rawText.slice(0, 15000)}
        `);

        return {
            statusCode: 200,
            body: JSON.stringify(
                {
                    source: targetUrl,
                    data: result
                }
            ),
        }
    } catch (error: any) {
        console.error("Orchestration error:", error);
        return {
            statusCode: 500,
            body: JSON.stringify({ error: error.message }),
        };
    }
};