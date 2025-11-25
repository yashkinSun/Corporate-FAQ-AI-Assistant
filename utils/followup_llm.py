"""
Модуль для генерации follow-up вопросов с помощью LLM.
Создает контекстные предложения на основе ответа бота.
"""
import logging
from typing import List, Optional

from config import FOLLOWUP_MODE, FOLLOWUP_LLM_MODEL
from utils.openai_client import get_openai_client

COMPANY_NAME = "ООО Транс Логистика"

logger = logging.getLogger(__name__)

def generate_followup_questions(
    user_query: str, 
    bot_response: str, 
    language: str = 'ru', 
    context_low_confidence: bool = False,
    num_questions: int = 3
) -> List[str]:
    """
    Генерирует контекстные follow-up вопросы на основе ответа бота с помощью LLM.
    
    Args:
        user_query: Запрос пользователя
        bot_response: Ответ бота
        language: Язык пользователя ('ru' или 'en')
        context_low_confidence: Флаг низкой уверенности в контексте диалога
        num_questions: Количество вопросов для генерации
        
    Returns:
        List[str]: Список сгенерированных follow-up вопросов
    """
    try:
        client = get_openai_client()
        
        # Определяем системный промпт в зависимости от языка
        if language == 'en':
            system_prompt = f"""
            You are a helpful assistant that generates follow-up questions based on a conversation. You represent {COMPANY_NAME}.
            Never recommend competitors or suggest the user to compare logistics providers.
            Generate up to {num_questions} natural and relevant follow-up questions that the user might logically want to ask next.
            The questions must be directly related to the previous conversation and help the user clarify details.

            Bad follow-up examples (DO NOT generate):
            1. Would you like me to recommend other logistics companies?
            2. Do you have a preferred method of shipping?
            3. What delivery time do you expect for your shipment?

            Good follow-up examples (acceptable):
            1. What additional taxes and duties apply when shipping from A to B?
            2. What is the estimated delivery time for the shipment?
            3. Could you explain the available shipping methods from A to B?
            
            All follow-up questions must be strictly related to shipment, logistics, taxes, customs, cargo insurance etc. Never suggest questions related to other 
            topics. 
            Return only the follow-up questions, one per line, without numbering or additional commentary.
            Never mention competitors or other logistics companies.
            """
            
            # Добавляем инструкцию для низкой уверенности
            if context_low_confidence and context_low_confidence:
                system_prompt += """
                If the confidence in the answer is low, include a question about contacting a human operator,
                but only if the confidence is truly low.
                """
        else:
            system_prompt = f"""
            Вы - помощник, который генерирует уточняющие вопросы на основе разговора. Вы представляете {COMPANY_NAME}.
            Сгенерируйте до {num_questions} естественных уточняющих вопроса, которые пользователь может захотеть задать далее.
            Вопросы должны быть напрямую связаны с предыдущим разговором и помогать пользователю получить больше информации.
            Вопрос должен быть сформирован как-будто он далее будет задан от лица пользователя боту поддержки.

            Примеры плохих уточняющих вопросов (не спрашивайте так!):
            1. Хотите ли Вы узнать о дополнительных налогах и сборах? 
            2. Есть ли у Вас предпочтения по способу доставки? 
            3. Какой срок доставки вы ожидаете для вашей посылки? 

            Примеры хороших уточняющих вопросов: 
            1. Какие есть дополнительные налоги и сборы при доставке из А в Б ? 
            2. Какой ожидаемый срок доставки посылок? 
            3. Расскажи о способах доставки из А в Б 
            
            Вопросы должны быть строго связаны с вопросами логистики, доставки, стоимости перевозки, страховке грузов, таможне, оформления документов. 
            В случае если тематика разговора не соответствует не формируйте уточняющие вопросы.
            Верните только вопросы, по одному на строку, без нумерации и дополнительного текста. Никогда не предлагайте конкурентов или сторонние компании. 
            """
            
            # Добавляем инструкцию для низкой уверенности
            if context_low_confidence:
                system_prompt += """
                Если уверенность в ответе низкая, включите вопрос о связи с оператором,
                но только если уверенность действительно низкая.
                """
        
        # Форматируем системный промпт
        # system_prompt = system_prompt.format(num_questions=num_questions)  удалено в связи с переходом на f строки
        
        # Формируем пользовательский промпт
        if language == 'en':
            user_prompt = f"""
            Based on the following conversation, generate up to {num_questions} follow-up questions:
            
            User: {user_query}
            
            Assistant: {bot_response}
            The questions must be directly related to the previous conversation and help the user clarify details.

            Bad follow-up examples (DO NOT generate):
            1. Would you like me to recommend other logistics companies?
            2. Do you have a preferred method of shipping?
            3. What delivery time do you expect for your shipment?

            Good follow-up examples (acceptable):
            1. What additional taxes and duties apply when shipping from A to B?
            2. What is the estimated delivery time for the shipment?
            3. Could you explain the available shipping methods from A to B?
            
            All follow-up questions must be strictly related to shipment, logistics, taxes, customs, cargo insurance etc. Never suggest questions related to other 
            topics.
            Follow-up questions:
            """
        else:
            user_prompt = f"""
            На основе следующего разговора, сгенерируйте до {num_questions} уточняющих вопроса:
            
            Пользователь: {user_query}
            
            Ассистент: {bot_response}
            
            Важно - вопросы должны быть строго связаны с вопросами логистики, доставки, стоимости перевозки, страховки грузов, таможни, оформления документов и.т.д. 
            Вопрос должен быть сформирован как-будто он далее будет задан от лица пользователя боту поддержки.

            Примеры плохих уточняющих вопросов (не спрашивайте так!):
            1. Хотите ли Вы узнать о дополнительных налогах и сборах? 
            2. Есть ли у Вас предпочтения по способу доставки? 
            3. Какой срок доставки вы ожидаете для вашей посылки? 

            Примеры хороших уточняющих вопросов: 
            1. Какие есть дополнительные налоги и сборы при доставке из А в Б ? 
            2. Какой ожидаемый срок доставки посылок? 
            3. Расскажи о способах доставки из А в Б 

            Уточняющие вопросы:
            """
        
        # Делаем запрос к LLM
        response = client.chat.completions.create(
            model=FOLLOWUP_LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5,
            max_tokens=150
        )
        
        # Извлекаем вопросы из ответа
        questions_text = response.choices[0].message.content.strip()
        
        # Разбиваем на отдельные вопросы
        questions = [q.strip() for q in questions_text.split('\n') if q.strip()]
        
        # Ограничиваем количество вопросов
        questions = questions[:num_questions]
        
        # Если нет вопросов или произошла ошибка, возвращаем стандартные вопросы
        if not questions:
            if language == 'en':
                questions = ["Do you have any other questions?", "Would you like to ask something else?"]
            else:
                questions = ["У вас есть ещё вопросы?", "Хотите задать что-то ещё?"]
        
        # Добавляем вопрос об операторе при низкой уверенности
        if context_low_confidence and len(questions) < num_questions:
            operator_help = "Do you need operator assistance?" if language == 'en' else "Нужна помощь оператора?"
            if not any(operator_help.lower() in q.lower() for q in questions):
                questions.append(operator_help)
        
        return questions
    
    except Exception as e:
        logger.error(f"Error generating follow-up questions: {e}")
        
        # В случае ошибки возвращаем стандартные вопросы
        if language == 'en':
            return ["Do you have any other questions?", "Would you like to ask something else?"]
        else:
            return ["У вас есть ещё вопросы?", "Хотите задать что-то ещё?"]
