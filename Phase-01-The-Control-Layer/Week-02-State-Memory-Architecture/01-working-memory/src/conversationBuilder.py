import tiktoken
import os
import json
from pydantic import BaseModel

encoding = tiktoken.encoding_for_model("gpt-4o-mini")

class MessageObject(BaseModel):
    role: str
    content: str

class ConversationBuilder():
    def __init__(self, token_limit=4000, metrics_file="conversation_metrics.json"):
        self.token_limit = token_limit
        self.metrics_file = metrics_file
        self.conversation: list[MessageObject] = []
        self.current_tokens = 0
        self.load_and_trim_conversation()

    def load_full_conversation(self):
        if os.path.exists(self.metrics_file):
            with open(self.metrics_file, "r") as f:
                data = json.load(f)
                self.token_limit = data.get("token_limit", self.token_limit)
                return [MessageObject(**msg) for msg in data.get("conversation", [])]
        return []

    def load_and_trim_conversation(self):
        '''
        This function is used to load the metrics for the current instance from a json file.
        '''
        full_converation = self.load_full_conversation()

        self.conversation = []
        self.current_tokens = 0

        for msg in full_converation:
            self.conversation.append(msg)
            self.current_tokens += self.estimate_tokens(msg.content)
            while self.current_tokens > self.token_limit:
                for i, m in enumerate(self.conversation):
                    if m.role != "system":
                        self.current_tokens -= self.estimate_tokens(m.content)
                        del self.conversation[i]
                        break
                else:
                    break

    def save_metrics(self):
        '''
        This function is used to save the metrics for the given message. It is used to save the metrics of the current instance to a json file.
        '''
        if os.path.exists(self.metrics_file):
            with open(self.metrics_file, "r") as f:
                data = json.load(f)
        else:
            data = {"conversation": []}

        data["current_tokens"] = self.current_tokens
        data["token_limit"] = self.token_limit

        with open(self.metrics_file, "w") as f:
            json.dump(data, f, indent=2)

    def append_message_to_file(self, message):
        if os.path.exists(self.metrics_file):
            with open(self.metrics_file, "r") as f:
                data = json.load(f)
                messages = data.get("conversation", [])
        else:
            messages = []
            data = {}

        messages.append(message.model_dump())
        data["conversation"] = messages

        with open(self.metrics_file, "w") as f:
            json.dump(data, f, indent=2)

    def estimate_tokens(self, message):
        '''
        Estimates the amount of tokens the given message is comprised off using the tiktoken library. This is important to ensure that we do not exceed the token limit when adding messages to the conversation.
        '''
        return len(encoding.encode(message))

    def add_message(self, role, content):
        '''
        Adds a message to the conversation. It then checks to see if the message can be added to the sliding window without exceeding our token limit. If we exceed our token limit, we remove the oldest messages from the conversation until we are back within the token limit. This ensures that we can continue to add messages to the conversation without exceeding the token limit. System messages are never removed.
        '''
        message = MessageObject(role=role, content=content)
        self.append_message_to_file(message)
        self.load_and_trim_conversation()
        self.save_metrics()

    def token_sliding_window(self):
        '''
        This function is used to update the conversation using the sliding window algorithm with the latest messages from the conversation. It should be called after adding a new message to the conversation. It will remove the oldest messages from the conversation until we are back within the token limit. System messages are never removed.
        '''
        while self.current_tokens > self.token_limit:

            for i, message in enumerate(self.conversation):
                if message.role != "system":
                    message_tokens = self.estimate_tokens(message.content)
                    self.current_tokens -= message_tokens
                    del self.conversation[i]
                    break
            else:
                break

    def format_prompt(self):
        '''
        Formats the prompt to put the system messages first, then the user messages, and finally the assistant messages. This is the format that the OpenAI API expects.
        '''
        system_messages = [message for message in self.conversation if message.role == "system"]
        user_messages = [message for message in self.conversation if message.role == "user"]
        assistant_messages = [message for message in self.conversation if message.role == "assistant"]

        formatted_prompt = []
        for message in system_messages + user_messages + assistant_messages:
            formatted_prompt.append({"role": message.role, "content": message.content})
        return formatted_prompt

if __name__ == "__main__":
    conversation_builder = ConversationBuilder()

    # conversation_data = json.load(open("conversation_data.json", "r"))

    # for msg in conversation_data:
    #     conversation_builder.add_message(role=msg["role"], content=msg["content"])

    conversation_builder.add_message("user", "Thank you. I think that is all I need.")
    conversation_builder.add_message("assistant", "You're welcome! If you have any more questions in the future, feel free to ask. Have a great day!")

    print(conversation_builder.format_prompt())
    print(f"Current tokens: {conversation_builder.current_tokens}")
    print(f"Token Limit: {conversation_builder.token_limit}")