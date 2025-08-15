
from transformers import pipeline

# Use transformer-based sentiment analysis for mood
sentiment_classifier = pipeline("sentiment-analysis", model="cardiffnlp/twitter-roberta-base-sentiment-latest")
emotion_classifier = pipeline("text-classification", model="j-hartmann/emotion-english-distilroberta-base", top_k=1)


def analyze_text(text):
    # Use transformer-based sentiment analysis for mood
    sentiment_result = sentiment_classifier(text)
    sentiment_label = sentiment_result[0]['label'].lower()
    if sentiment_label == 'positive':
        mood = "Positive"
    elif sentiment_label == 'negative':
        mood = "Negative"
    else:
        mood = "Neutral"

    emotion_result = emotion_classifier(text)
    emotion = emotion_result[0][0]['label']

    suggestion = get_detailed_suggestion(mood, emotion)

    return {
        'mood': mood,
        'emotion': emotion,
        'suggestion': suggestion
    }

def get_detailed_suggestion(mood, emotion):
    mood_suggestions = {
        "Positive": "Keep up the good vibes! Share your joy, and keep doing what makes you happy.",
        "Negative": "Take a deep breath. Consider a short walk, journaling, or talking to someone you trust.",
        "Neutral": "A quiet moment or a short meditation could help you reflect and recharge."
    }
    emotion_suggestions = {
        "joy": "Celebrate your wins! Enjoy the moment and spread positivity.",
        "sadness": "It's okay to feel sad. Take a break, do something comforting, or reach out to a friend.",
        "anger": "Try a breathing exercise or a quick walk to release tension. Express your feelings constructively.",
        "fear": "You're not alone — talk to a friend, write your thoughts down, or practice grounding techniques.",
        "love": "Express your love! Connect with someone or share kind words.",
        "surprise": "Channel the surprise into curiosity. What can you learn from this experience?",
        "neutral": "Reflect calmly. A clear mind is a powerful tool.",
        "happy": "Enjoy your happiness! Share it with others and do something fun.",
        "sad": "Take care of yourself. Try activities that comfort you and talk to someone if needed."
    }
    # Combine mood and emotion advice for more detail
    mood_advice = mood_suggestions.get(mood, "Take care of yourself!")
    emotion_advice = emotion_suggestions.get(emotion.lower(), "Take care of your emotional well-being.")
    return f"{mood_advice} {emotion_advice}"