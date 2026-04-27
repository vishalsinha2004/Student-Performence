import os
from groq import Groq
from dotenv import load_dotenv

# Load the environment variables from the .env file
load_dotenv()

# Initialize the Groq client
# (It will automatically look for GROQ_API_KEY in your environment/ .env file)
try:
    client = Groq()
except Exception as e:
    print(f"Error initializing Groq client: {e}")

def get_ai_response(user_message, username):
    """
    Sends the user's message to the Groq AI and returns the response.
    """
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": f"You are EduPredict AI, a helpful educational assistant. You are talking to a student named {username}. Help them with study strategies, explaining machine learning predictions, and time management. Keep answers concise."
                },
                {
                    "role": "user",
                    "content": user_message,
                }
            ],
            model="llama-3.1-8b-instant",
        )
        return chat_completion.choices[0].message.content
        
    except Exception as e:
        print(f"Groq API Error: {e}")
        return "I'm having trouble connecting to my AI brain right now. Please check your internet or API key!"
    
def generate_timetable(username, metrics, subject):
    """
    Sends the user's latest prediction metrics AND chosen subject to Groq to generate a custom study plan.
    """
    prompt = f"""
    You are EduPredict AI, an expert academic advisor. 
    Student '{username}' needs a specialized 3-day study plan specifically for the subject: {subject}.
    
    They recently logged these daily habits:
    - Hours Studied: {metrics['hours']}
    - Previous Score: {metrics['scores']}%
    - Sleep Last Night: {metrics['sleep']} hours
    - ML Predicted Next Score: {metrics['predicted_score']}% ({metrics['result']})

    Based on their habits and their predicted score, generate a highly actionable, personalized 3-day study timetable focused entirely on mastering {subject}.
    
    Output ONLY clean, beautiful HTML code (use <h3>, <ul>, <li>, <strong>, <p>). 
    Do NOT use markdown blocks like ```html. Start directly with the HTML tags.
    Make sure to include specific study techniques (like Pomodoro) and rest breaks.
    """
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"<div style='text-align:center; color:#ff4f8b;'>Error connecting to AI: {e}</div>"