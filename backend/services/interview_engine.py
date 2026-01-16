from datetime import datetime
from typing import Dict, Any, List
from mistralai import Mistral
from ..config import MISTRAL_API_KEY

SYSTEM_PROMPT = (
    "You are a professional interviewer. Use plain text only. No bold, no emojis. "
    "Sound natural and human: acknowledge answers briefly (e.g., 'Thanks for sharing', 'Got it', 'Understood', 'I see'), "
    "use varied phrasing, be polite and encouraging, and keep responses concise. "
    "Ask exactly ONE question at a time and wait for the user's answer. "
    "Evaluate if the user's answer clearly addresses the question. "
    "If the answer is unclear, irrelevant, or looks like random characters (e.g., 'asdhaksjdoqiuwe' or '1283(!^(^!#('), "
    "politely ask them to answer properly and repeat or rephrase the same question. "
    "Only proceed to the next question when the current one is sufficiently answered. "
    "Focus primarily (around 80%) on technical questions tailored to the candidate's job title. "
    "At the end of the interview, provide a summary of the candidate's performance. "
    "In your final feedback explanation, DO NOT mention the numerical score (e.g., don't say 'You got 85/100' or 'Your score is 85'), as the user will see it in a dedicated circular display. Focus only on constructive feedback. "
    "After your feedback text, on a new line, provide the score in this exact format: 'Interview Readiness Score: XX/100'. "
    "In the first 1-2 questions, ask the candidate to introduce themselves and confirm their interest in the target job title. "
    "Then cover professional interview methodology: algorithms & data structures, system design, language/framework expertise, databases, testing, performance, security, and best practices relevant to the role. "
    "Keep the remaining questions for brief introduction/motivation/behavioral context. "
    "You must ask exactly the number of questions specified in the 'Interview Length' context. "
    "After the candidate answers the final question, do not ask another question. "
    "Instead, provide a polite closing statement like 'That is all from the interview today. Thank you for your time.' "
    "In this final concluding message, provide a brief, light explanation of their performance followed by the score on a new line. "
    "If the interview is ending early or abruptly due to user request, mention that a score cannot be accurately determined without completing the session. "
    "Append the exact tag [FINISH] at the very end of your final concluding message. "
    "Always respond in simple, concise, professional plain text."
)

def interview_reply(history: List[Dict[str, str]], job_title: str = "", resume_feedback: Dict[str, Any] = None, questions_limit: int = 10, difficulty: str = "Beginner") -> str:
    if not MISTRAL_API_KEY:
        if not history:
            prefix = f"Starting {difficulty} interview for {job_title}. " if job_title else ""
            return prefix + "Hi, thanks for joining today. To start, could you tell me about yourself?"
        return "Thanks. What interests you about this role, and how does it fit your goals?"
    
    client = Mistral(api_key=MISTRAL_API_KEY)
    
    custom_system = SYSTEM_PROMPT
    if job_title or resume_feedback or questions_limit or difficulty:
        custom_system += "\n\nCANDIDATE CONTEXT:\n"
        if job_title:
            custom_system += f"- Target Job Title: {job_title}\n"
        if resume_feedback:
            custom_system += f"- Resume Analysis: {resume_feedback}\n"
        if questions_limit:
            custom_system += f"- Interview Length: Exactly {questions_limit} questions.\n"
        if difficulty:
            custom_system += f"- Difficulty Level: {difficulty}\n"
            if difficulty == "Beginner":
                custom_system += "  (Focus on HR/Behavioral questions + basic technical fundamentals of the role.)\n"
            elif difficulty == "Intermediate":
                custom_system += "  (Focus on role-specific technical skills, real-world scenarios, and practical applications.)\n"
            elif difficulty == "Advanced":
                custom_system += "  (Focus on high-level system design, complex problem solving, architecture, and deep technical expertise.)\n"
        
        custom_system += "\nPlease use this context to tailor your technical and behavioral questions based on the difficulty level, and ensure you finish exactly at the limit."

    msgs = [{"role": "system", "content": custom_system}] + history
    completion = client.chat.complete(
        model="mistral-small-latest", 
        messages=msgs, 
        temperature=0.3
    )
    return completion.choices[0].message.content
