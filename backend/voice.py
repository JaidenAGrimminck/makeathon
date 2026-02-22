# get env
import os
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai.types import HttpOptions
from google.genai import types

import wave

# Set up the wave file to save the output:
def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
   with wave.open(filename, "wb") as wf:
      wf.setnchannels(channels)
      wf.setsampwidth(sample_width)
      wf.setframerate(rate)
      wf.writeframes(pcm)

class Voice:
    def __init__(self):
        self.client = genai.Client()

    def ask(self, text):
        # just a basic example of using Gemini to generate a text response (can be used for chatbot or to generate prompts for TTS)
        response = self.client.models.generate_content(
            model="gemini-2.5-flash-preview",
            contents=f"Answer the following question in a concise and clear manner: {text}",
            config=types.GenerateContentConfig(
                response_modalities=["TEXT"],
            ),
        )

        return response.candidates[0].content.parts[0].text
    
    def text_to_speech(self, text, mood, filename="voice_lines/output.wav"):
        response = self.client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=f"Say {mood}: {text}",
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name='Iapetus',
                        )
                    )
                ),
            )
        )
        
        data = response.candidates[0].content.parts[0].inline_data.data

        wave_file(filename, data)

if __name__ == "__main__":
    voice = Voice()
    voice.text_to_speech("You are so stupid and crazy and a son of a gun.", "in a very angry mood", "test.wav")
        