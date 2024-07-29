import requests
import os
from pyairtable import Table
from openai import OpenAI


SERP_API_KEY = ""
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AIRTABLE_API_KEY = ""
AIRTABLE_BASE_ID = "appjFY4nD28B6gfmA"
AIRTABLE_TABLE_NAME = "tblJomhoQ5ShIcnDN"
print(SERP_API_KEY)

airtable = Table(AIRTABLE_API_KEY, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)
#openai_client = OpenAI(api_key=OPENAI_API_KEY)

def scrape_google(query):
    url = "https://serpapi.com/search.json"
    params = {
        "api_key": SERP_API_KEY,
        "q": query,
        "num": 5  # Number of results to fetch
    }
    response = requests.get(url, params=params)
    data = response.json()
    print(data)
    
    # Check for different possible keys
    if 'organic_results' in data:
        return data['organic_results']
    elif 'results' in data:
        return data['results']
    else:
        print(f"Unexpected response structure: {data.keys()}")
        return [] 

def summarize_text(text, prompt):
#    response = openai_client.chat.completions.create(
#        model="gpt-3.5-turbo",
#        messages=[
#            {"role": "system", "content": prompt},
#            {"role": "user", "content": text}
#        ]
#    )
#    return response.choices[0].message.content
    return "hello"

def rewrite_text(text, prompt):
#    response = openai_client.chat.completions.create(
#        model="gpt-3.5-turbo",
#        messages=[
#            {"role": "system", "content": prompt},
#            {"role": "user", "content": text}
#        ]
#    )
#    return response.choices[0].message.content
    return "Hello"

def markdown_to_html(markdown_text):
    html = markdown_text.replace('#', '<h1>').replace('\n', '<br>')
    return html

def main():
    records = airtable.all()
    for record in records:
        topic = record['fields'].get('Topic')
        if topic:
            #Scrape Google search results
            search_results = scrape_google(topic)
            
            #Store source URLs in Airtable
            urls = [result['link'] for result in search_results]
            airtable.update(record['id'], {'Source URLs': ', '.join(urls)})
            
            #Summarize content
            summary_prompt = "Summarize the following text:"
            full_text = ' '.join([result['snippet'] for result in search_results])
            summary = summarize_text(full_text, summary_prompt)
            
            #Rewrite text (translate to French)
            rewrite_prompt = "Translate the following text to French:"
            rewritten_text = rewrite_text(summary, rewrite_prompt)
            
            #Stores final result in markdown
            markdown_result = f"# {topic}\n\n{rewritten_text}"
            
            html_result = markdown_to_html(markdown_result)
            
            # Store results in Airtable
            airtable.update(record['id'], {
                'Summary': summary,
                'Rewritten Text': rewritten_text,
                'Markdown Result': markdown_result,
                'HTML Result': html_result
            })

if __name__ == "__main__":
    main()