import { SecretsManagerClient, GetSecretValueCommand } from "@aws-sdk/client-secrets-manager";
import { ChatOpenAI } from "@langchain/openai";
import { DynamoDBChatMessageHistory } from "@langchain/community/stores/message/dynamodb";
import { ChatPromptTemplate, MessagesPlaceholder } from "@langchain/core/prompts";
import { RunnablePassthrough, RunnableWithMessageHistory } from "@langchain/core/runnables";
import { StringOutputParser } from "@langchain/core/output_parsers";

const secretsClient = new SecretsManagerClient({ region: "us-east-1" });

const secretResponse = await secretsClient.send(
    new GetSecretValueCommand({ SecretId: "dev/openai/ai-engineering-lab" })
)
const secrets = JSON.parse(secretResponse.SecretString || "{}");
const key = secrets.OPENAI_API_KEY;

const model = new ChatOpenAI({
    apiKey: key,
    modelName: "gpt-4o-mini",
    temperature: 0,
});

const prompt = ChatPromptTemplate.fromMessages([
    ["system", "You are a concise project management assistant."],
    new MessagesPlaceholder("chat_history"),
    ["human", "{input}"],
]);

const chain = RunnablePassthrough.assign({
    chat_history: (input: any) => input.chat_history.slice(-20)
})
.pipe(prompt)
.pipe(model)
.pipe(new StringOutputParser());

const chainWithHistory = new RunnableWithMessageHistory({
    runnable: chain,
    getMessageHistory: (sessionId) =>
        new DynamoDBChatMessageHistory({
            tableName: "ProjectManagerHistory",
            partitionKey: "SessionId",
            sessionId,
            config: { region: "us-east-1" },
        }),
        inputMessagesKey: "input",
        historyMessagesKey: "chat_history",
});

export const handler = async (event: any) => {
    if (!event.body) {
        return {
            statusCode: 400,
            body: JSON.stringify({ error: "Missing request body" }),
        };
    }

    let body;
    try {
        body = typeof event.body === "string" ? JSON.parse(event.body) : event.body;
    } catch (e) {
        return {
            statusCode: 400,
            body: JSON.stringify({ error: "Malformed JSON in request body." }),
        };
    }

    const { sessionId, input } = body;

    if (!sessionId || !input) {
        return {
            statusCode: 400,
            body: JSON.stringify({ error: "Missing sessionId or input in request body." }),
        };
    }

    const response = await chainWithHistory.invoke(
        { input },
        { configurable: { sessionId } }
    );

    return {
        statusCode: 200,
        body: JSON.stringify({ response }),
    };
};