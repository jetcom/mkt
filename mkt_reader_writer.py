#!/usr/bin/env python3
from configobj import ConfigObj, Section
import os

root_path = "../questions/"
questionPool_path = "/questionPool/"


def get_courses():
    courses = [name for name in os.listdir(root_path)
            if os.path.isdir(os.path.join(root_path, name))]
    courses.sort()
    return courses

def get_questions_files(course):
    files = os.listdir(root_path+course+questionPool_path)
    files.sort()
    return str(files).strip('[]')


def load_questions_file(course, question_file):
    f_name = root_path + course + questionPool_path + question_file
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
    
def get_question(questions, file, title):
    key = file+"/"+title
    return questions[key]
    
def update_question(question, key, value):
    question[key] = value
    
def save_changes(f_name, obj):
    obj.write(open(f_name, "wb"))

if __name__ == "__main__":
    if not os._exists("../questions/"):
        root_path = "./questions/"
    obj, questions = load_questions_file("csci320-2191", "chapter1.txt")
    question = get_question(questions, 'chapter1.txt', 'File System')
    update_question( question, 'points', 100)
    save_changes('test.txt', obj)

