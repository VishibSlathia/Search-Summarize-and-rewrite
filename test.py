import requests
import os
from pyairtable import Api
from openai import OpenAI
from serpapi import google_search # I didn't really use this as it was getting super complicated and requests.get does the job insanely well.
from bs4 import BeautifulSoup

# API Keys and Configuration
SERP_API_KEY = "b731ec8c47824b66cbdc2700976f0d078c0328dacbd77df24c4ad120c74b19aa"
OPENAI_API_KEY = ""
AIRTABLE_API_KEY= "patwm8JXKpGwh3tnD.e4e4826201df911e56e0b2e019f52b675a7cb58275f33e5288f1ed4ae3a8c275"
AIRTABLE_BASE_ID = "appjFY4nD28B6gfmA"
AIRTABLE_TABLE_NAME = "tblJomhoQ5ShIcnDN"

# Initialize APIs
airtable_api = Api(AIRTABLE_API_KEY)
airtable = airtable_api.table(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)

openai_client = OpenAI(api_key=OPENAI_API_KEY)

def scrape_google(query, num_results=5):
    url = "https://serpapi.com/search.json"
    params = {
        "api_key": SERP_API_KEY,
        "engine": "google",
        "q": query,
        "num": num_results,
        "location": "United States",
        "google_domain": "google.com",
        "gl": "us",
        "hl": "en"
    }
    response = requests.get(url, params = params)
    results = response.json()
    
    if 'organic_results' in results:
        return [result['link'] for result in results['organic_results']]
    else:
        print(f"Unexpected response structure: {results.keys()}")
        return []

def get_text(link):
    try:
        response = requests.get(link)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        text = ""
        for element in soup.find_all(['p', 'span', 'div']):
            text += element.get_text() + " "
        
        print(f"Retrieved content from: {link}")
        return text.strip()
    except Exception as e:
        print(f"Error retrieving content from {link}: {str(e)}")
        return ""

def generate_text(prompt, text, model="gpt-3.5-turbo"):
    print(f"Generating text for prompt: {prompt[:50]}...")
    try:
        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text}
            ],
            temperature=1,
            max_tokens=4095,
            frequency_penalty=0.0
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error generating text: {str(e)}")
        return ""

def parse_markdown_text(markdown):
    output = []
    current_heading = None
    current_body = ""

    for line in markdown.split('\n'):
        if line.startswith("## "):
            if current_heading:
                output.append({"heading": current_heading, "text": current_body.strip()})
            current_heading = line
            current_body = ""
        else:
            current_body += line.strip() + " "
    
    if current_heading:
        output.append({"heading": current_heading, "text": current_body.strip()})
    
    return output

def main():
    records = airtable.all()
    for record in records:
        topic = record['fields'].get('Topic')
        if topic:
            #Scrape Google search results
            urls = scrape_google(topic)
            if urls:
                airtable.update(record['id'], {'Source URLs': ', '.join(urls)})
                print(f"Added {len(urls)} URLs for topic: {topic}")
            else:
                print(f"No URLs found for topic: {topic}")
                continue
            #Get text from scraped URLs
            full_text = ""
            for url in urls:
                content = get_text(url)
                if content:
                    full_text += content + "\n\n"

            if not full_text:
                print(f"No content retrieved for topic: {topic}")
                continue
            
            #Summarize content
            summary_prompt = f"In the input are articles from other websites. Summarise each article in one paragraph for {topic}. List H2 title + article summary. Output should be in standard markdown format"
            summary = generate_text(summary_prompt, full_text)
            
            #Rewrite text (translate to French)
            rewrite_prompt = f"Translate the following text for {topic} to French. Provide your output in standard markdown text but do not enclose the results in a code block."
            rewritten_text = generate_text(rewrite_prompt, summary)
            
            #Parse markdown and store results
            parsed_markdown = parse_markdown_text(rewritten_text)
            markdown_result = "\n\n".join([f"{section['heading']}\n\n{section['text']}" for section in parsed_markdown])
            
            #Store results in Airtable
            airtable.update(record['id'], {
                'Summary': summary,
                'Rewritten Text': rewritten_text,
                'Markdown Result': markdown_result
            })
            
            print(f"Processed topic: {topic}")

if __name__ == "__main__":
    main()