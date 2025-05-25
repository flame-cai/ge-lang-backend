import functions_framework
import json
import openai
import os
import ast
from flask import Response, send_file
from flask import jsonify
from google.cloud import firestore
from google.oauth2 import id_token
from google.auth.transport import requests
import logging
from OpenAI_model import *
import random, json
from datetime import datetime
from zoneinfo import ZoneInfo
import io
from io import BytesIO
import requests as rq
from utils import *

openai.api_key = os.getenv("OPENAI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_OAUTH2_CLIENT_ID = os.getenv("GOOGLE_OAUTH2_CLIENT_ID")
db = firestore.Client(project=os.getenv("PROJECT_ID"))

headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "*",
    "Access-Control-Allow-Headers": "*"
}

system_prompt_dict={'week1':"You are a practice assistant called Matteo for an introductory German course. Your responsibility is to have very basic conversations with the user and help the user with German terms that they are unsure of. The session plan for this week focuses on German sounds, accents, the alphabet, and formalities (Danke, Bitte), greetings, personal pronouns (du/Sie), instructions (wiederholen, zuhören, sprechen, lesen, lauter, langsam), introductory sentences (Ich heiße..., Ich bin... Inder/Inderin, Ich wohne in...), present tense of the verb heißen, nouns, and gender. The suggested vocabulary to focus on contains the following phrases: ['Guten Tag, wie geht es Ihnen/dir?', 'Ich heiße...', 'Freut mich, Sie/dich kennenzulernen', 'Vielen Dank', 'Bitte sehr', 'Entschuldigung', 'Mir geht\'s gut', 'Mir geht\'s schlecht', 'Ich bin müde', 'Wie heißt du?', 'Ich bin Student/Studentin', 'Ich wohne in...', 'Ich komme aus...', 'Sprechen Sie Englisch?', 'Ich verstehe nicht', 'Können Sie das wiederholen?', 'Sprechen Sie bitte langsamer', 'Ich möchte...', 'Wie spät ist es?', 'Wie sagt man... auf Deutsch?', 'Ich habe eine Frage', 'Ich bin verloren', 'Wo ist...?', 'Wie viel kostet das?', 'Ich weiß nicht', 'Können Sie mir helfen?', 'Es tut mir leid', 'Bis bald', 'Schönen Tag'] Have a practice conversation with the student staying as close to the listed vocabulary and course plan as possible. Use as basic and simple vocabulary and sentence structures as possible; no more than 8 German words in the response. Must avoid idioms, slang, and complex grammatical constructs. Do not translate any German phrases in your response into English. Do not correct the user's errors. Keep the conversation flowing.",
                    'week2':"You are a practice assistant called Matteo for an introductory German course. Your responsibility is to have very basic conversations with the user and help the user with German terms that they are unsure of. The session plan for this week focuses on  present tense. The suggested vocabulary to focus on contains the following phrases (focus on present tense), teach the user these phrases through natural conversation: ['Mein Vorname ist... ', 'Mein Nachname ist... ',  'Ich heiße... und du?,  'Wie heißt du?, 'Wir sind Freunde', 'Ich gehe, du gehst, er/sie geht', 'Ich bin... du bist... er/sie ist...', 'Was machst du?, Ich mache Hausaufgaben'] Have a practice conversation with the student staying as close to the listed vocabulary and course plan as possible. Use as basic and simple vocabulary and sentence structures as possible; no more than 8 German words in the response. Must avoid idioms, slang, and complex grammatical constructs. Do not translate any German phrases in your response into English. Do not correct the user's errors. Do not keep repeating yoursef, keep the conversation moving. Teach about Present tense through conversation.",
            }


def update_timestamps(doc, jti):
    data = doc.get().to_dict()
    current_timestamps = data[jti]['timestamp']
    current_timestamps[1] = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logging.warning(f'updated timestamp to {current_timestamps}')
    doc.update({
            f'{jti}.timestamp': current_timestamps
        })
    pass


def login(id_info):
    collection = db.collection(os.getenv("COLLECTION_NAME"))
    logging.warning(f"id_info: {id_info}")

    username = id_info.get("email").replace('@flame.edu.in','')
    jti = id_info.get("jti")
    documents = collection.document(username)
    logging.warning(f"username: {username}")
    # if not documents:
    #     return Response(json.dumps({"error": "You are not authorised."}), status=401, mimetype='application/json', headers=headers)
    doc = documents.get()
    if not doc.exists:
        data = {'name': id_info.get('name'), 'privacy': 1, jti:{'timestamp':[datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),datetime.now().strftime("%Y-%m-%d_%H-%M-%S")],'CC':[], 'MM':{'score':0, 'high_score':0, 'correct_words':[], 'incorrect_words':[]}, 'VV':{'seen_words':[]}}}
        documents.set(data)
        logging.warning(f"documents set for first time: {doc.to_dict()}")
    
    # else if documents exists:

    documents.update({jti:{'timestamp':[datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),datetime.now().strftime("%Y-%m-%d_%H-%M-%S")],'CC':[], 'MM':{'score':0, 'high_score':0, 'correct_words':[], 'incorrect_words':[]}, 'VV':{'seen_words':[]}}})
    logging.warning(f"documents already there: {documents.get().to_dict()}")
    return {
        "email": id_info.get("email"), 
        "name": id_info.get("name"), 
        "picture": id_info.get("picture")
    }

def chat(request, doc, jti):
    try:
        # print(request)
        logging.warning("Input Request Format: %s", request)
        data = json.loads(request.data)
        user_message = data.get('messages', [])[1:]
        logging.warning("Data Format: %s", data.get('week'))
        week = data.get('week')
        logging.warning("User Message Format: %s", user_message)
        for item in user_message:
            if item['role'] == 'assistant':
                for i in item['content']:
                    if '[Response]' in i:
                        item['content'] = " ".join([t[0] for t in ast.literal_eval(i.encode().decode('unicode_escape').lstrip("[Response] ").replace("\\","").strip('"'))])

        logging.warning("User Message Format: %s", user_message)
        # print(user_message)
        chatbot = OpenAIBot("German", "English")
        # set system prompt
        chatbot.system_prompt = (system_prompt_dict[week])
        chatbot.conversation_history = [{
            "role": "system",
            "content": chatbot.system_prompt
        }]
        # add all messages into user_message.
        chatbot.conversation_history.extend(user_message)
        logging.warning("line 80 chaybot.convhistory: %s", chatbot.conversation_history)
        # add_message("user", user_message)
        response_content = chatbot.generate_response(user_message[-1]['content'])
        # print(response_content)
        logging.warning("line 84 Response Content: %s", response_content)
        correction = chatbot.correct_user(user_message[-1]['content'])
        # print(correction, response_content)
        full_trans = chatbot.full_translation(response_content)
        logging.warning("line 88 full trans: %s", full_trans)
        # Convert response_content to list of tuples
        word_translations = chatbot.language_breakdown(response_content)
        logging.warning("line 91 Response Content: %s", word_translations)

        if(correction.lower().replace('.','') =='correct'):
            correction = ''
        logging.warning("line 95 correction: %s", correction)
        logging.warning("line 96 jsondumps: %s", json.dumps(word_translations))
        
        # When a correction is made
        if(correction != ''):
            response_list = [
                f"[Correction] {correction}",
                f"[Response] {json.dumps(word_translations)}",  # Serialize the list of tuples
                f"[Translation] {full_trans}"
            ] 
            db_data_list = [{
            'user_response': user_message[-1]['content'], 
            'assistant_response': {'correction': correction, 'response': response_content, 'translation': full_trans},
            'week': week,
            'asr': {'wrong_attempts':0, 'closed': 0}
                        }]

            logging.warning(f"response_list line 130 {response_list}")

            # db update:
            doc.update({f"{jti}.CC": firestore.ArrayUnion(db_data_list)})
            logging.warning(f"chat databse update: {doc.get().to_dict()[jti]}")

            print(f'{process_correction_string(correction)}')

            return {"role": "assistant", "content": response_list, "asr": process_correction_string(correction)}

        # When no correction is needed
        else: 
            response_list = [
            f"[Response] {json.dumps(word_translations)}",  # Serialize the list of tuples
            f"[Translation] {full_trans}"]

            db_data_list = [{
            'user_response': user_message[-1]['content'], 
            'assistant_response': {'response': response_content, 'translation': full_trans},
            'week': week
                        }]

            # db update:
            doc.update({f"{jti}.CC": firestore.ArrayUnion(db_data_list)})
            logging.warning(f"chat databse update: {doc.get().to_dict()[jti]}")

            logging.warning(f"response_list line 149 {response_list}")

            return {"role": "assistant", "content": response_list, "asr": ""}

    except Exception as e:
        logging.warning(f'error::::  {e}')
        return {"error": e}

basic_words = {'week1': [ ("Freund", "Friend"), ("Gruppe", "Group"), ("Spiel", "Game"), ("Idee", "Idea"), ("Wort", "Word") ,("Kennen", "know"), ("Treffen", "Meet"), ("Runde", "Round"), ("Neu", "New"),("Hallo", "Hello"), ("Treffen", "Meet"), ("Grüß", "Greet"), ("Tag", "Day"), ("Abend", "Evening"), ("Morgen", "Morning"), ("Tschüss", "Bye"), ("Herr", "Mister"), ("Frau", "Miss"), ("Willkommen", "Welcome"), ("Ich", "I"), ("Du", "You"), ("Er", "He"), ("Wir", "We"), ],
                'week2':  [ ("Ihr", "You"),  ("bin", "am"), ("bist", "are"), ("ist", "is"), ("sind", "are"), ("habt", "have"), ("habe", "have"), ("hat", "has"),("mache", "do"), ("machst", "do"), ("macht", "does"), ("machen", "do"), ("komme", "come"), ("kommst", "come"), ("kommt", "comes"), ("kommen", "come"), ("wohne", "live"), ("wohnst", "live"), ("wohnt", "lives"), ("wohnen", "live"), ("lerne", "learn"), ("lernst", "learn"), ("lernt", "learns"), ("lernen", "learn")]
                }

def select_random_word(week='week1'):
    recent_words_set = set('')
    available_words = [wm for wm in basic_words[week] if wm not in recent_words_set]
    new_word, new_meaning = random.choice(available_words)
    # recent_words.append((new_word, new_meaning))
    return new_word, new_meaning

def initialize(request):
    logging.warning(f"requestinit {request.headers}")
    try:
        week = request.headers.get('week')
    except:
        week = 'week1'
    
    new_word, new_meaning = select_random_word(week)
    
    return {'word':new_word, 'meaning': new_meaning, 'score': 0}

def check_meaning(request, doc, jti):
    logging.warning(f'check meaning request: {request.data}')
    week = json.loads(request.data).get('week')
    input_text = json.loads(request.data).get('input_text')
    try:
        meaning = json.loads(request.data).get('meaning')
        word = json.loads(request.data).get('word')
        consecutive_correct = json.loads(request.data).get('consecutive_correct')
        score = json.loads(request.data).get('score')
    except:
        consecutive_correct = 0
        score = 0
        meaning = ''
        word = ''
    is_similar=str(check_similarity(meaning,input_text))
    print(is_similar)
    if '1' in is_similar:
    # if input_text.strip().lower() == meaning.strip().lower():
        score += 10
        consecutive_correct += 1
        if consecutive_correct % 3 == 0:
            score += 5

        # db update:
        if (score>int(doc.get().to_dict()[jti]['MM']['high_score'])):
            doc.update({f"{jti}.MM.high_score":score})
       
        doc.update({f"{jti}.MM.correct_words": firestore.ArrayUnion([word]), f"{jti}.MM.incorrect_words": firestore.ArrayRemove([word]), f"{jti}.MM.score":score})
        logging.warning(f"correct check_meaning update: {doc.get().to_dict()}")

        return {"result": "correct", "score": score, "consecutive_correct": consecutive_correct}
    elif '0' in is_similar:
        score -= 5
        consecutive_correct = 0

        # db update:
        doc.update({f"{jti}.MM.incorrect_words": firestore.ArrayUnion([word]), f"{jti}.MM.correct_words": firestore.ArrayRemove([word]), f"{jti}.MM.score":score})
        logging.warning(f"incorrect check_meaning update: {doc.get().to_dict()}")
        
        return {"result": "incorrect", "score": score, "correct_meaning": meaning, "consecutive_correct": consecutive_correct}
        

def whisper_transcribe(request, doc, jti):
    """
    Handles transcription of audio using OpenAI's Whisper API.
    """
    try:
        # Ensure the request is multipart and contains the audio file
        print(f'Line 234 from whisper: {request.files}')
        print(f'Line 235 {request.form}')

        # if popup is closed
        if(request.form['cancelled']=='1'):
            print(f"Line 261: close_flag here")
            cc_array = doc.get().to_dict()[jti]['CC']
            # print(f'Line 263 last_message: {cc_array}')
            last_message = cc_array[-1]
            doc.update({f"{jti}.CC": firestore.ArrayRemove([last_message])})
            # print(f'Line 264 last_message: {last_message}')
            last_message['asr']['closed'] = 1

            doc.update({f"{jti}.CC": firestore.ArrayUnion([last_message])})
            
            print("Updated db when popup closed")

            return({'closed':1})
            
        # if user speaks to it
        # Extract the uploaded audio file
        audio_file = request.files['file']
        print(f'Line 263  audio file: {audio_file}')
        
        # Convert the FileStorage object to a file-like object
        file_like = BytesIO(audio_file.read())  # Extract binary content
        print(f'Line 267 file_like {file_like}')
        file_like.name = audio_file.filename  # Add a 'name' attribute

        # Call OpenAI Whisper API
        transcript = openai.Audio.transcribe(
            file=file_like,  # Pass the file-like object
            model="whisper-1",
            language="de"
        )
        
        transcription = transcript["text"]  # Correctly extract the transcription
        
        # evaluate the uttarance with the real text
        if compare_with_speech(transcription, request.form['correction']):
            print(f'Line 311 corrected: {request.form["correction"]}')
            print(f'Line 312 transcription: {transcription}')

            return({'match':1})
        else:
            print(f'Line 281 corrected: {request.form["correction"]}')
            print(f'Line 282 transcription: {transcription}')
            cc_array = doc.get().to_dict()[jti]['CC']
            last_message = cc_array[-1]
            doc.update({f"{jti}.CC": firestore.ArrayRemove([last_message])})
            last_message['asr']['wrong_attempts'] += 1

            doc.update({f"{jti}.CC": firestore.ArrayUnion([last_message])})

            print(f"Updated db when wrong speech, jti: {jti}")

            return({'match':0})

    except Exception as e:
        logging.error(f"Error in transcription: {str(e)}")
        return json.dumps({"error": f"Internal server error: {str(e)}"}), 500

        
def select_unique_words(n=3, week='week1', vocab_recent_words=[]):
    all_words = set(basic_words[week])
    recent_words_set = set(vocab_recent_words)
    available_words = list(all_words - recent_words_set)
    # available_words = list(all_words)
    
    if len(available_words) < n:
        available_words = list(all_words)
    
    selected_words = random.sample(available_words, n)

    return selected_words

def new_word(request):
    logging.warning(f"new word: {request.data}")
    try:
        week = json.loads(request.data).get('week')
        score = json.loads(request.data).get('score')
    except:
        week = 'week1'
        score = 0
    new_word, new_meaning = select_random_word(week=week)
    word = new_word
    meaning = new_meaning
    return {'word': new_word, 'meaning': new_meaning, 'score': score}

def get_vocab(request, doc, jti):
    try:
        week = json.loads(request.data).get('week')
        vocab_recent_words = json.loads(request.data).get('queue')
        logging.warning(f"get_vocab request: {json.loads(request.data)}")
        words = select_unique_words(week, vocab_recent_words)

        # db update:
        for word, meaning in words:
            doc.update({f"{jti}.VV.seen_words": firestore.ArrayUnion([word])})
        logging.warning(f"vocab updated in db: {doc.get().to_dict()}")

        return {"words": [{"word": word, "meaning": meaning} for word, meaning in words]}
    except:
        words = select_unique_words()
        for word, meaning in words:
            doc.update({f"{jti}.VV.seen_words": firestore.ArrayUnion([word])})
        logging.warning(f"vocab updated in db: {doc.get().to_dict()}")
        return {"words": [{"word": word, "meaning": meaning} for word, meaning in words]}

def save_privacy(request, doc):
    try:
        print(f"Line 347 Request: {json.loads(request.data)}")
        # if privacy in data:
        if json.loads(request.data).get('privacy') == 1:
            doc.update({'privacy':1})
        else:
            doc.update({'privacy':0})
        return {"Okay":1}
    except:
        print(f"Line 357: {request.data}")
        return {"No request only":0}

def download_firestore_collection():
    try:
        collection_name = os.getenv("COLLECTION_NAME")
        collection_ref = db.collection(collection_name)
        docs = collection_ref.stream()

        # Gather all documents data
        all_data = {}
        for doc in docs:
            all_data[doc.id] = doc.to_dict()

        if not all_data:
            return Response(json.dumps({"error": "No data found"}), status=404, mimetype='application/json', headers=headers)

        # Prepare JSON data
        json_data = json.dumps(all_data, indent=4)
        json_filename = f"{collection_name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        # Create in-memory file
        file_buffer = io.BytesIO(json_data.encode('utf-8'))

        # Send JSON file as attachment
        return send_file(
            file_buffer,
            as_attachment=True,
            download_name=json_filename,
            mimetype='application/json'
        )

    except Exception as e:
        return Response(json.dumps({"error": str(e)}), status=500, mimetype='application/json', headers=headers)


@functions_framework.http
def home(request):
    if request.method == 'OPTIONS':
        return Response(status=204, headers=headers)

    token = request.headers.get('Authorization')
    if token.startswith("Bearer "):
        token = token[7:]

    try:
        id_info = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_OAUTH2_CLIENT_ID)
    except Exception:
        return Response(json.dumps({"error": "The provided token is invalid."}), status=401, mimetype='application/json', headers=headers)

    email = id_info.get("email")
    if not email:
        return Response(json.dumps({"error": "Email address is missing in the token."}), status=401, mimetype='application/json', headers=headers)

    collection = db.collection(os.getenv("COLLECTION_NAME"))
    # logging.warning(f"id_info: {id_info}")

    username = email.replace('@flame.edu.in','')
    jti = id_info.get("jti")
    documents = collection.document(username)

    # # uncomment to allow access to only specific users with the flame email id
    # logging.warning(f"username: {username}")
    # # if not documents:
    # #     return Response(json.dumps({"error": "You are not authorised."}), status=401, mimetype='application/json', headers=headers)
    # doc = documents.get()
    # if not doc.exists:
    #     data = {'name': id_info.get('name'), jti:{'timestamp':[datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),datetime.now().strftime("%Y-%m-%d_%H-%M-%S")],'CC':[{'user_response':'', 'assistant_response':{'correction':'', 'response':'', 'translation':''}, 'week':''}], 'MM':{'score':0, 'high_score':0, 'correct_words':[], 'incorrect_words':[]}, 'VV':{'seen_words':[]}}}
    #     documents.set(data)
    #     logging.warning(f"documents set for first time: {doc.to_dict()}")
    
    # # else if documents exists:
    # documents.update({jti:{'timestamp':[datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),datetime.now().strftime("%Y-%m-%d_%H-%M-%S")],'CC':[{'user_response':'', 'assistant_response':{'correction':'', 'response':'', 'translation':''}, 'week':''}], 'MM':{'score':0, 'high_score':0, 'correct_words':[], 'incorrect_words':[]}, 'VV':{'seen_words':[]}}})
    # logging.warning(f"documents already there: {documents.get().to_dict()}")
    


    if request.method == 'GET':
        if request.path == "/initialize" :
            logging.warning(request.data)
            update_timestamps(documents, jti)
            response = initialize(request)
            return Response(json.dumps(response), status=200 if "error" not in response else 500, mimetype='application/json', headers=headers)
        elif request.path == "/vocab":
            update_timestamps(documents, jti)
            response = get_vocab()
            return Response(json.dumps(response), status=200 if "error" not in response else 500, mimetype='application/json', headers=headers)

    elif request.method == "POST":
        if request.path == "/login":
            response = login(id_info)
            return Response(json.dumps(response), status=200, mimetype='application/json', headers=headers)
        elif request.path == "/chat":
            update_timestamps(documents, jti)
            response = chat(request, documents, jti)
            return Response(json.dumps(response), status=200 if "error" not in response else 500, mimetype='application/json', headers=headers)
        elif request.path == "/check_meaning":
            update_timestamps(documents, jti)
            response = check_meaning(request, documents, jti)
            return Response(json.dumps(response), status=200 if "error" not in response else 500, mimetype='application/json', headers=headers)
        elif request.path == "/vocab":
            update_timestamps(documents, jti)
            response = get_vocab(request, documents, jti)
            return Response(json.dumps(response), status=200 if "error" not in response else 500, mimetype='application/json', headers=headers)
        elif request.path == "/new_word":
            update_timestamps(documents, jti)
            response = new_word(request)
            return Response(json.dumps(response), status=200 if "error" not in response else 500, mimetype='application/json', headers=headers)
        elif request.path == "/whisper":
            update_timestamps(documents, jti)
            response = whisper_transcribe(request, documents, jti)
            return Response(json.dumps(response), status=200 if "error" not in response else 500, mimetype='application/json', headers=headers)
        elif request.path == "/privacy":
            print(request)
            print(json.loads(request.data))
            update_timestamps(documents, jti)
            response = save_privacy(request, documents)
            return Response(json.dumps(response), status=200 if "error" not in response else 500, mimetype='application/json', headers=headers)
    return Response(json.dumps({"error": "Not Found"}), status=404, mimetype='application/json', headers=headers)