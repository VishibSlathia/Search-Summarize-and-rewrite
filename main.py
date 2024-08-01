import requests
import os
from pyairtable import Api
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import google.generativeai as genai

# API Keys and Configuration
SERP_API_KEY = "b731ec8c47824b66cbdc2700976f0d078c0328dacbd77df24c4ad120c74b19aa"
GEMINI_API_KEY = "AIzaSyBh8fREoUx5fdlQUfZVQXmqAH3wN5Otoe4"  # Your Gemini API key
AIRTABLE_API_KEY= "patwm8JXKpGwh3tnD.e4e4826201df911e56e0b2e019f52b675a7cb58275f33e5288f1ed4ae3a8c275"
AIRTABLE_BASE_ID = "appjFY4nD28B6gfmA"
AIRTABLE_TABLE_NAME = "tblJomhoQ5ShIcnDN"

# Initialize APIs
airtable_api = Api(AIRTABLE_API_KEY)
airtable = airtable_api.table(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME)
genai.configure(api_key=GEMINI_API_KEY)

# Flask app setup
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///content.db'
db = SQLAlchemy(app)

# Database model
class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Article {self.title}>'

# Create the database
with app.app_context():
    db.create_all()

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
    response = requests.get(url, params=params)
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

def generate_text(prompt, text):
    print(f"Generating text for prompt: {prompt[:50]}...")
    try:
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(f"{prompt}\n\n{text}")
        return response.text
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

def create_article(title, content):
    new_article = Article(title=title, content=content)
    db.session.add(new_article)
    db.session.commit()
    return new_article.id

def main():
    records = airtable.all()
    for record in records:
        topic = record['fields'].get('Topic')
        if topic:
            # Scrape Google search results
            urls = scrape_google(topic)
            if urls:
                airtable.update(record['id'], {'Source URLs': ', '.join(urls)})
                print(f"Added {len(urls)} URLs for topic: {topic}")
            else:
                print(f"No URLs found for topic: {topic}")
                continue

            # Get text from scraped URLs
            full_text = ""
            for url in urls:
                content = get_text(url)
                if content:
                    full_text += content + "\n\n"

            if not full_text:
                print(f"No content retrieved for topic: {topic}")
                continue
            
            # Summarize content
            summary_prompt = f"In the input are articles from other websites. Summarise each article in one paragraph for {topic}. List H2 title + article summary. Output should be in standard markdown format"
            summary = generate_text(summary_prompt, full_text)
            
            # Generate a full article
            article_prompt = f"Based on the following summary, write a comprehensive article about {topic}. Include an introduction, main points, and a conclusion. Use markdown formatting for headings and subheadings."
            article = generate_text(article_prompt, summary)

            # Parse markdown and store results
            parsed_markdown = parse_markdown_text(article)
            markdown_result = "\n\n".join([f"{section['heading']}\n\n{section['text']}" for section in parsed_markdown])
            
            # Create article in the database
            with app.app_context():
                article_id = create_article(topic, markdown_result)
            
            # Store results in Airtable
            airtable.update(record['id'], {
                'Summary': summary,
                'Full Article': article,
                'Article ID': article_id
            })
            
            print(f"Processed topic: {topic} and created article with ID: {article_id}")

# Flask routes
@app.route('/')
def index():
    articles = Article.query.order_by(Article.date_created.desc()).all()
    return render_template('index.html', articles=articles)

@app.route('/article/<int:id>')
def article(id):
    article = Article.query.get_or_404(id)
    return render_template('article.html', article=article)

@app.route('/generate', methods=['GET', 'POST'])
def generate():
    if request.method == 'POST':
        topic = request.form['topic']
        # Here you would call your main function or a modified version of it
        # to generate content for the given topic
        # For now, let's just create a dummy article
        with app.app_context():
            article_id = create_article(topic, f"This is a generated article about {topic}")
        return redirect(url_for('article', id=article_id))
    return render_template('generate.html')

if __name__ == "__main__":
    main()  # Generate initial content
    app.run(debug=True)  # Start the Flask server