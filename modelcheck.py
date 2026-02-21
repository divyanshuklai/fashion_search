from google import genai
import os
from dotenv import load_dotenv
from pprint import pprint
load_dotenv()

key = os.environ.get('GEMINI_API_KEY')
c = genai.Client(api_key=key)
pprint([model.name for model in c.models.list()[:]])
