#!/usr/bin/env python3
import os
import glob

from os.path import exists, isdir, isfile, join
from configobj import ConfigObj, Section

MAX_QUESTIONS = "maxQuestions"

root_path = "../courses/"
questions_path = "/questions/"
# questionPool_path = "/questionPool/"

def get_folders(course):
    folders = [x[0] for x in os.walk(root_path + course + questions_path)]
    folders_trimmed = list(map(lambda folder : folder.replace(root_path + course, '').strip('/'), folders))
    return trim_array(folders_trimmed)

def get_courses():
    courses = [name for name in os.listdir(root_path)
            if isdir(join(root_path, name))]
    courses.sort()
    return courses

def get_exams(course):
    path = root_path + course
    exams = [f for f in os.listdir(path) if isfile(join(path, f))]
    exams.sort()
    return trim_array(exams).replace(".ini", "")

def get_question_files(course, exam):
    path = root_path + course + questions_path
    questions = [f for f in glob.glob(path + '**', recursive=True) if isfile(f)]
    questions.sort()
    return trim_array(questions).replace(path, '')

def load_questions_file(course, question_file):
    f_name = root_path + course + questions_path + question_file
    obj = ConfigObj(f_name, interpolation=True)
    f_name = f_name.split("/")
    f_name = f_name[len(f_name)-1]
    return load_questions(obj, f_name)

def load_questions(obj, parent):
    qList = {}    

    for c in obj:
        if MAX_QUESTIONS == c:
            continue

        item = obj[c]
        if "question" in item:
            qList[c] = item
        elif isinstance(item, Section):
            qList.update(load_questions(item, c))
    return qList
    
def get_question(questions, file, title):
    key = file+"/"+title
    return questions[key]
    
def update_question(question, key, value):
    question[key] = value
    
def save_changes(f_name, obj):
    obj.write(open(f_name, "wb"))

def read_question_file(file):
    return 'Hello World'

def create_category(name, course, path):
    new_category = root_path + course + "/" + path + "/" + name
    if exists(new_category):
        raise Exception
    f = open(new_category, "w+")
    f.close()
    return 'Success'

def create_section(name, course, path):
    new_section = root_path + course + "/" + path + "/" + name
    if exists(new_section):
        raise Exception
    os.makedirs(new_section)
    return 'Success'

def trim_array(arr):
    return str(arr).strip('[]').replace("'", "")

if __name__ == "__main__":
    if not os._exists("../questions/"):
        root_path = "./questions/"
    obj, questions = load_questions_file("csci320-2191", "chapter1.txt")
    question = get_question(questions, 'chapter1.txt', 'File System')
    update_question( question, 'points', 100)
    save_changes('test.txt', obj)

