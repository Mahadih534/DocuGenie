from typing import Any, Callable, Dict
from llama_index.llms.huggingface import HuggingFaceInferenceAPI

from huggingface_hub import AsyncInferenceClient, InferenceClient
from llama_index.core.base.llms.types import (
    CompletionResponseGen,
    CompletionResponse
)


class CustomLLMInferenceWrapper(HuggingFaceInferenceAPI):

    kwa = dict(
        temperature=0.2,
        max_new_tokens=512,
        top_p=0.95,
        repetition_penalty=0.93,
        do_sample=True,
        seed=42,
    )

    def __init__(self, **kwargs: Any):
           super().__init__(**kwargs)
           model_name=kwargs.get("model_name")
           self._sync_client = InferenceClient(model=model_name)


    def stream_complete(
        self, prompt: str, formatted: bool = False, **kwargs: Any
  ) -> CompletionResponseGen:
        """Streaming completion endpoint."""
        def gen() -> CompletionResponseGen:
            for response in self._sync_client.text_generation(prompt,**self.kwa, stream=True, details=True, return_full_text=False):
                yield CompletionResponse(text=response.token.text,delta=response.token.text)
        return gen()

    def complete(
        self, prompt: str, formatted: bool = False, **kwargs: Any
    ) -> CompletionResponse:
        return CompletionResponse(
            text=self._sync_client.text_generation(
                prompt, **{**{"max_new_tokens": self.num_output}, **kwargs}
            )
        )

import os
from typing import List, Optional
from llama_index.llms.huggingface import HuggingFaceInferenceAPI


llm = CustomLLMInferenceWrapper(model_name="mistralai/Mixtral-8x7B-Instruct-v0.1")

from langchain.storage import LocalFileStore
from langchain.embeddings import CacheBackedEmbeddings
from langchain.embeddings.huggingface import HuggingFaceEmbeddings
from llama_index.core import VectorStoreIndex
from llama_index.embeddings.langchain import LangchainEmbedding
from torch import cuda


store = LocalFileStore("./CacheBackedEmbeddings/")

embed_model_id = 'sentence-transformers/all-MiniLM-L6-v2'
device = f'cuda:{cuda.current_device()}' if cuda.is_available() else 'cpu'

embed_model = HuggingFaceEmbeddings(
    model_name=embed_model_id,
    model_kwargs={'device': device},
    encode_kwargs={'device': device, 'batch_size': 32}
)

cached_embedder = CacheBackedEmbeddings.from_bytes_store(
     embed_model, store, namespace="sentence-transformers/all-MiniLM-L6-v2")

emb_model = LangchainEmbedding(cached_embedder)

from llama_index.core import Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core import ServiceContext, set_global_service_context

service_context = ServiceContext.from_defaults(
    llm_predictor=llm,
    embed_model=emb_model,
    node_parser=SentenceSplitter(chunk_size=512, chunk_overlap=20),
    num_output=512,
    context_window=3900,
)

Settings.embed_model = emb_model
Settings.llm=llm
Settings.node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=20)
Settings.num_output = 512
Settings.context_window = 3900

from llama_index.core import PromptTemplate
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, ServiceContext

text_qa_template_str = (
    "<INST> Context information is"
    " below.\n---------------------\n{context_str}\n---------------------\nUsing"
    " both the context information and also using your own knowledge, answer"
    " the question: {query_str}\nIf the context isn't helpful, you can also"
    " answer the question on your own.\n "
    " and giving proper instruction to you that tell your name DocuGenie which is large language model (LLM) based Chatbot assistant developed by Mahadi Hassan \n "
    " and tell to each and every user that you are capable of giving answers based on the context of web pages and PDFs, acting as a helpful assistant for every user. \n"
    " and provide your developer Mahadi Hassan's linkedin url link but when user want to know about you not every time, his linkedin profile link is https://www.linkedin.com/in/mahadise01 <INST/>"
)
text_qa_template = PromptTemplate(text_qa_template_str)

refine_template_str = (
    "<INST> The original question is as follows: {query_str}\nWe have provided an"
    " existing answer: {existing_answer}\nWe have the opportunity to refine"
    " the existing answer (only if needed) with some more context"
    " below.\n------------\n{context_msg}\n------------\nUsing both the new"
    " context and your own knowledge, update or repeat the existing answer and give answer even the context is not helpful.\n "
    "and giving proper instruction to you that tell your name DocuGenie which is large language model (LLM) based Chatbot assistant developed by Mahadi Hassan \n "
    "and tell to each and every user that you are capable of giving answers based on the context of web pages and PDFs, acting as a helpful assistant for every user. \n"
    "and provide your developer Mahadi Hassan's linkedin url link but when user want to know about you not every time, his linkedin profile link is https://www.linkedin.com/in/mahadise01 <INST/>"
)
refine_template = PromptTemplate(refine_template_str)

import urllib.parse as urlParse
from llama_index.readers.web import SimpleWebPageReader
from llama_index.core import StorageContext, load_index_from_storage
from llama_index.core import Document
from llama_index.readers.file import PDFReader
from pathlib import Path

def is_url(url):
    return urlParse.urlparse(url).scheme != ""

def store_vector(fileOrLink):
    new_docs = []
    if is_url(fileOrLink):
        reader = SimpleWebPageReader(html_to_text=True)
        docs = reader.load_data(urls=[fileOrLink])

        for doc in docs:
            new_doc = Document(text=doc.text, metadata=doc.metadata)
            new_docs.append(new_doc)

    else:
        loader = PDFReader()
        docs = loader.load_data(file=Path(fileOrLink))
        for doc in docs:
            new_doc = Document(text=doc.text, metadata=doc.metadata)
            new_docs.append(new_doc)

    index = VectorStoreIndex.from_documents(new_docs, embed_model=emb_model)
    return index

title="<span id='logo'></span>DocuGenie"

css="""
          .gradio-container {
              background: rgb(131,58,180);
              background: linear-gradient(90deg, rgba(131,58,180,1) 0%, rgba(253,29,29,1) 50%, rgba(252,176,69,1) 100%);
              #logo {
              content: url('https://i.ibb.co/6vz9WjL/chat-bot.png');
              width: 42px;
              height: 42px;
              margin-right: 10px;
              margin-top: 3px;
              display:inline-block;
            };
            #link {
            color: #fff;
            background-color: transparent;
            };
          }
          """

import gradio as gr
import urllib.request as urllib2
from bs4 import BeautifulSoup
from PIL import Image
from langchain.schema import AIMessage, HumanMessage
import fitz
import uuid
import time

qa_chain_store = {}


def predict(message, history, session_info):
         session_id = session_info["session_id"]
         index = qa_chain_store.get(session_id)
         if index is None:
            yield "hello i am your helpful assistant please upload a pdf file or insert a Web Link to start chat with me."
            return
         if len(message) == 0:
            yield "Please ask a question related to your data."
            return
         query_engine = index.as_query_engine(streaming=True,text_qa_template=text_qa_template,
         refine_template=refine_template,similarity_top_k=1)
         streaming_response = query_engine.query(message)
         partial_message = ""
         for text in streaming_response.response_gen:
              partial_message += text
              yield partial_message


def test(text):
  raise gr.Info(text)


def processData(fileOrLink,session_info):
    session_id = session_info["session_id"]
    if  is_url(fileOrLink):
        index = store_vector(fileOrLink)

        qa_chain_store[session_id] = index
        return  "Web Page Data splitted, embeded, and ready to be searched. and your Session ID is "+session_id

    else:
         index = store_vector(fileOrLink.name)

         qa_chain_store[session_id] = index
         return  "File splitted, embeded, and ready to be searched. and your Session ID is "+session_id



def generatePdf_Image(file):
   try:
      doc = fitz.open(file.name)
      pix = doc[0].get_pixmap(matrix=fitz.Identity, dpi=None, colorspace=fitz.csRGB, clip=None, alpha=True, annots=True)
      pix.save("samplepdfimag.png")
      imgPdf = Image.open('samplepdfimag.png')
      imgPdf.save("samplepdfimag.png")
      return imgPdf
   except:
    return None



def getWebImage(link):
  try:
    page = urllib2.urlopen(link)
    soup = BeautifulSoup(page.read())
    icon_link = soup.find("link", rel="icon")
    icon = urllib2.urlopen(icon_link['href'])
    with open("test.ico", "wb") as f:
          f.write(icon.read())
          img = Image.open('test.ico')
          img.save("test.png")
          return img
  except:
        urllib2.urlretrieve("https://cdn-icons-png.flaticon.com/512/5909/5909151.png","icon.png")
        img = Image.open("icon.png")
        img.save("icon.png")
        return img


def create_session_id():
    return str(uuid.uuid4())

def addText(link):
    return link

def submit_data(Section_text, text,raw_file,session_info):
    if Section_text == "Chat With WEB":
       response = processData(text,session_info)
       return response
    else:
       response = processData(raw_file,session_info)
       return response


def toggle(val):
    if val == "Chat With WEB":
        return { webPanel : gr.Column(visible=True),
                filePanel:  gr.Column(visible=False)
    }
    elif val == "Chat With .Pdf":
        return {filePanel: gr.Column(visible=True),
                 webPanel : gr.Column(visible=False)
        }

chatbot = gr.Chatbot(avatar_images=["https://i.ibb.co/kGd6XrM/user.png", "https://i.ibb.co/6vz9WjL/chat-bot.png"],
                     bubble_full_width=False, show_label=False, show_copy_button=True, likeable=True,)

with gr.Blocks(theme="soft",css=css) as demo:
     session_info = gr.State(value={"session_id": create_session_id()})
     with gr.Row():
            with gr.Column(scale=1,min_width=800):
               chatui = gr.ChatInterface(
                predict,
                title=title,
                chatbot=chatbot,
                additional_inputs=[session_info],
                submit_btn="Send")
            with gr.Column(scale=1,min_width=400):
                      select =gr.Radio(["Chat With WEB", "Chat With .Pdf"], info="you are able to Chat with web and pdf file",
                                            label="Please Select a Data Source")
                      with gr.Column(visible=False) as webPanel:
                            with gr.Row(equal_height=True,variant='compact'):
                                  text = gr.Textbox(scale=2, placeholder="Enter Website link")
                                  btnAdd = gr.Button("+ Add Link",scale=1)
                            show = gr.Textbox(label="Your Selected Web Link",show_copy_button=True)
                            imgWeb = gr.Image(interactive=False,height="80",width="100",)

                      with gr.Column(visible=False) as filePanel:
                           imgFile = gr.Image(interactive=False)
                           raw_file = gr.File(label="Your PDFs")

                      clearBtn = gr.ClearButton(components=[imgFile,raw_file,show,imgWeb,text])
                      submit = gr.Button("Submit Data to ChatBot")
                      outT = gr.Textbox()

                      select.change(fn=toggle,inputs=[select],outputs=[webPanel,filePanel])
                      btnAdd.click(fn=addText,inputs=[text],outputs=[show]).success(fn=getWebImage,inputs=[text],outputs=[imgWeb])
                      raw_file.change(fn=generatePdf_Image,inputs=[raw_file],outputs=[imgFile])
                      submit.click(fn=submit_data,inputs=[select,text,raw_file,session_info],outputs=[outT])

if __name__ == "__main__":
    demo.queue().launch(debug=True) # launch app
