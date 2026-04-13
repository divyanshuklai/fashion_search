from google import genai
from pprint import pprint 
from dotenv import load_dotenv

load_dotenv()

client = genai.Client()

response = client.models.generate_content(
    model = "gemma-4-31b-it", contents="FOLLOW THE INSTRUCTIONS CAREFULLY AND ONLY GENERATE A PARSABLE JSON STRING, DO NOT INCLUDE BACKTICKS AND OTHER FORMATTING:\n" \
    "generate a MongoDB JSON query to display the total amount " \
    "purchased of every product in the collection storedb.product_sales " \
    "given each document has price and quantity sold."
)

print(response.text)