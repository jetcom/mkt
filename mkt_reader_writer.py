#!/usr/bin/env python3
from configobj import ConfigObj, Section

def load_questions_file(f_name):
   obj = ConfigObj(f_name, interpolation=True)   
   f_name = f_name.split("/")
   f_name = f_name[len(f_name)-1]
   return obj, load_questions(obj, f_name)

def load_questions(obj, parent):
    qList = {}    
    for c in obj:
        item = obj[c]
        if "question" in item:
            qList[parent + "/" + c] = item
        elif isinstance(item, Section):
            qList.update(load_questions(item, parent + "/" + c))
    return qList
    
def get_question(questions, key):
    return questions[key]
    
def update_question(question, key, value):
    question[key] = value
    
def save_changes(f_name, obj):
    obj.write(open(f_name, "wb"))

if __name__ == "__main__":
    obj, questions = load_questions_file("csci320-2191/questionPool/chapter1.txt")
    question = get_question(questions, 'chapter1.txt/File System')
    update_question( question, 'points', 100)
    save_changes('test.txt', obj)

