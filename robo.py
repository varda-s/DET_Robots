#IMPORT PACKAGES 
from __future__ import division

import re
import sys
import os
import config

from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types
import pyaudio 
import pygame 
from six.moves import queue

from gtts import gTTS
import time
from adafruit_crickit import crickit
from adafruit_seesaw.neopixel import NeoPixel

# Audio recording parameters, set for our USB mic.
RATE = 44100 # TODO change for DET mic 
CHUNK = int(RATE / 10)  # TODO change for DET mic 

#import credentials 
credential_path = "/home/pi/DET190-JSON/DETcredential.json" #TODO 
os.environ["GOOGLE_APPLICATION_CREDENTIALS"]=config.GOOGLE_AUTH

#THIS IS VERY IMPORTANT AS THE API LOOKS FOR IT 
client = speech.SpeechClient()

#initialize pygame so that we can run audio 
pygame.init()
pygame.mixer.init()


def playAudio(file):
    pygame.mixer.init()
    pygame.mixer.music.load(file)
    pygame.mixer.music.play()

#MicrophoneStream() is brought in from Google Cloud Platform
class MicrophoneStream(object):
    """Opens a recording stream as a generator yielding the audio chunks."""
    def __init__(self, rate, chunk):
        self._rate = rate
        self._chunk = chunk

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self):
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            # The API currently only supports 1-channel (mono) audio
            # https://goo.gl/z757pE
            channels=1, rate=self._rate,
            input=True, frames_per_buffer=self._chunk,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer,
        )

        self.closed = False

        return self
    
    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()    
   
   #the buffer is an array that holds the audio data (ie. from the stream)
    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        """Continuously collect data from the audio stream, into the buffer.""" #TODO THIS SHIT NEEDS TO BE CHANGED
        self._buff.put(in_data)
        return None, pyaudio.paContinue
    
    def generator(self):
            while not self.closed:
                # Use a blocking get() to ensure there's at least one chunk of
                # data, and stop iteration if the chunk is None, indicating the
                # end of the audio stream.
                chunk = self._buff.get()
                if chunk is None:
                    return
                data = [chunk]

                # Now consume whatever other data's still buffered.
                while True:
                    try:
                        chunk = self._buff.get(block=False)
                        if chunk is None:
                            return
                        data.append(chunk)
                    except queue.Empty:
                        break

                yield b''.join(data)
               


#this loop is where the microphone stream gets sent
def ListenPrintLoop(responses):
    """Iterates through server responses and prints them.

    The responses passed is a generator that will block until a response
    is provided by the server.

    Each response may contain multiple results, and each result may contain
    multiple alternatives; for details, see https://goo.gl/tjCPAU.  Here we
    print only the transcription for the top alternative of the top result.

    In this case, responses are provided for interim results as well. If the
    response is an interim one, print a line feed at the end of it, to allow
    the next result to overwrite it, until the response is a final one. For the
    final one, print a newline to preserve the finalized transcription.
    """
    num_chars_printed = 0
        
    for response in responses:
        
        if not response.results:
            continue

        # The `results` list is consecutive. For streaming, we only care about
        # the first result being considered, since once it's `is_final`, it
        # moves on to considering the next utterance.
        result = response.results[0]
        if not result.alternatives:
            continue

        # Display the transcription of the top alternative.
        transcript = result.alternatives[0].transcript

        overwrite_chars = ' ' * (num_chars_printed - len(transcript))

        if not result.is_final:
#            sys.stdout.write(transcript + overwrite_chars + '\r')
#            sys.stdout.flush()
            num_chars_printed = len(transcript)

        else:
            print(transcript + overwrite_chars)

            if re.search(r'\b(nice|cute|adorable|good)\b', transcript, re.I): 
                print("Positive words")
                playAudio("thanks.mp3") #TODO check the pathname on the pi 
                break
            elif re.search(r'(ugly|disgusting)', transcript, re.I):
                print("Negative words")
                playAudio("rude.mp3")

            num_chars_printed = 0

def Main():
    
    #initialize things 
    language_code = 'en-US'  # a BCP-47 language tag
    config = types.RecognitionConfig(
        encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code=language_code)
    streaming_config = types.StreamingRecognitionConfig(
        config=config,
        interim_results=True)

    t2s = gTTS('Thank you so much! That is really nice of you!', lang ='en')
    t2s.save('thanks.mp3')

    t2s1 = gTTS('Wow someone is rude! Why are you so mean dude', lang ='en')
    t2s1.save('rude.mp3')


  
    #mic set up to look for input and the info is sent to google for analysis 
    with MicrophoneStream(RATE, CHUNK) as stream:
        audio_generator = stream.generator()
        requests = (types.StreamingRecognizeRequest(audio_content=content)
                    for content in audio_generator)

        responses = client.streaming_recognize(streaming_config, requests)
        ListenPrintLoop(responses)

   

if __name__ == '__main__':
    Main()