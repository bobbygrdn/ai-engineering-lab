import { CheerioWebBaseLoader } from "@langchain/community/document_loaders/web/cheerio";
import { ChatOpenAI } from "@langchain/openai";
import "dotenv/config";
import { z } from "zod";
import fs from "fs";

export const TechStackSchema = z.object({
    postings: z.array(z.object({
        company: z.string().describe("The name of the company hiring"),
        role: z.string().describe("The job title"),
        tech_stack: z.array(z.string()).describe("List of technologies mentioned"),
        evidence: z.string().describe("The EXACT sentence or phrase from the text that proves this tech stack is required.")
    }))
});

async function runVerifiedScrape() {
    const loader = new CheerioWebBaseLoader("https://jobs.sevendaysvt.com/tech-jobs-vermont/");
    const docs = await loader.load();
    const rawText = docs.map(d => d.pageContent).join("\n\n");

    if (rawText.includes("404") || rawText.includes("page can't be found") || rawText.length < 500 ) {
        console.error("❌ ERROR: Data source is invalid or empty. Aborting LLM call to prevent hallucination.");
        return;
    }

    fs.writeFileSync("raw_scrape_debug.txt", rawText);
    console.log("Raw data saved to raw_scrape_debug.txt for inspection.");

    const model = new ChatOpenAI({
        modelName: "gpt-4o-mini",
        temperature: 0,
        apiKey: process.env.OPENAI_API_KEY
    }).withStructuredOutput(TechStackSchema);

    console.log("Extracting tech stacks with evidence...");

    const result = await model.invoke(`
        Extract technical job postings from the Burlington area.

        CRITICAL INSTRUCTION:
        For every 'tech_stack' you identify, you MUST provide the 'evidence'
        field. This must be a verbatim quote from the text below.

        DATA:
        ${rawText.slice(0, 15000)}
  `);

    console.dir(result, { depth: null });
}

runVerifiedScrape();