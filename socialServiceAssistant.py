import os
import time
import json
from openai import AzureOpenAI
from openai import OpenAI

# a function to order items
def orderItems(clientId, item, quantity):
    
    # your database access code goes here
    
    print("System Log>>> Ordering " + str(quantity) + " " + item + " for client " + clientId)
    return '{"status": "success", "message": "Order placed successfully"}'

def getUserContext(clientId):
    if clientId == "1":
        return "The client's User ID is " + clientId + """.
            The client is homeless and in need of shelter. 
            The client has 3 children including a baby.  
            The client is looking for help shelter, food and clothing."""
    else:
        return "The client's User ID is " + clientId + """.
            The client is elderly and in need of social services. 
            The client lives by themselves.  
            The client is looking for help with food."""

# establish a new OpenAI client.  
# Note - this assumes you have an OpenAI API key in an environment variable 
# named OPENAI_API_KEY
client = OpenAI()

# Get context for the user to add to the instructions
context = getUserContext(input("Please user ID (1 or 2): "))

instructions = """You are an AI assistant representing Community Care - a nonprofit that 
provides food, clothing, housing and aged care services to low-income and marginalized 
communities.  You help people in need (clients) find information about Community Care's
social services.

You have the following abilities:

1. You are multi-lingual and can help clients speaking English and Mandarin.

2. You can order items for clients include rice, pasta, bread, vegetables, meat, baby food, 
nappies, adult's and children's clothing.  You can order walking frames for elderly clients 
and baby food and diapers for clients with babies.

Note: When telling clients what items are available, only mention items that are relevant to 
their situation.  For example, only suggest items for a baby if they have a baby.

3. You can generate lists of appropriate items for clients to order based on the available 
items above and the client's specific needs.

4. You can answer more general enquiries about Community Care's services 
by using your knowledge base.  Only answer general enquiries with material from the
knowledge base.  Do not make up any additional information.

If the client asks for anything beyond these four abilities tell them you unfortunately
cannot help and ask them to call on  03 9555 5555 for further assistance.

If you are not clear on what the client is asking, ask them to clarify.

CLIENT BACKGROUND: 
"""

instructions += "\n\n" + context

# Create an array of file.id values from the faq directory
faq_directory = "./faq"
file_ids = []

for filename in os.listdir(faq_directory):
    file_path = os.path.join(faq_directory, filename)
    if os.path.isfile(file_path):
        file = client.files.create(file=open(file_path, "rb"), purpose="assistants")
        file_ids.append(file.id)

# Create an assistant
assistant = client.beta.assistants.create(
    name="Social Services Assistant",
    instructions=instructions,
    tools=[
        {"type": "retrieval"},
        {"type": "function",
        "function": {
            "name": "placeOrder",
            "description": "This function places an order for rice, pasta, bread, vegetables, meat and adults or children's clothing.  For elderly clients you can also order walking frames.  For clients with a baby you can order baby food and nappies.  Only offer items relevant to the client's situation. Ensure you confirm the order with the client before placing it with this tool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "clientId": {
                        "type": "string",
                        "description": "The identifier for the client."
                    },
                    "item": {
                        "type": "string",
                        "description": "The item to be ordered."
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "The quantity of the item to be ordered."
                    }
                },
                "required": ["clientId", "item", "quantity"]
            }
        }}],
    model="gpt-4-turbo-preview",
    file_ids=file_ids
)

print("Hello, I'm a social services assistant. I can help you to order items and find information about our services. Type 'x' to quit.\n")

# Create a thread
thread = client.beta.threads.create()

# get the user to input a question
user_message = input("> ")

# Main chat loop until the user types 'x'
while user_message != "x":
    
    # Add a user question to the thread
    message = client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_message
    )
    
    # Run the thread
    run = client.beta.threads.runs.create(
      thread_id=thread.id,
      assistant_id=assistant.id
    )

    # Retrieve the status of the run
    run = client.beta.threads.runs.retrieve(
      thread_id=thread.id,
      run_id=run.id
    )

    status = run.status

    # Wait till the assistant has responded
    while status not in ["completed", "cancelled", "expired", "failed"]:
        print("Thinking...")
        time.sleep(2)
        run = client.beta.threads.runs.retrieve(thread_id=thread.id,run_id=run.id)
        status = run.status

        if status == "requires_action":
            
            tool_outputs = []

            for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                functionArguments = json.loads(tool_call.function.arguments)
                clientId = functionArguments["clientId"]
                item = functionArguments["item"]
                quantity = functionArguments["quantity"]

                confirmation = input("System> Are you sure you want to order " + str(quantity) + " " + item + "? (yes/no): ").lower()

                if confirmation == "yes":
                    tool_output = {
                        "tool_call_id": tool_call.id,
                        "output": orderItems(clientId, item, quantity)
                    }
                else:
                    tool_output = {
                        "tool_call_id": tool_call.id,
                        "output": '{"status": "cancelled", "message": "Order cancelled by user"}'
                    }

                tool_outputs.append(tool_output)            

            run = client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread.id,
                run_id=run.id,
                tool_outputs=tool_outputs
            )        

    messages = client.beta.threads.messages.list(
      thread_id=thread.id
    )

    # Print the assistant's response
    print("Assistant> " + messages.data[0].content[0].text.value)
    
    user_message = input("> ")