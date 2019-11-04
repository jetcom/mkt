from flask import Flask, escape, request, render_template
import mkt_reader_writer 
import os
import json



app = Flask(__name__)

@app.route('/')
@app.route('/home')
def home():
    return render_template('home.html', courses=mkt_reader_writer.get_courses())

@app.route('/editor')
def editor():
    return render_template('editor.html', courses=mkt_reader_writer.get_courses())


@app.route('/changeCourse', methods=['POST'])
def changeCourse():
    course = request.form['selectedCourse']
    return mkt_reader_writer.get_exams(course)
    
@app.route('/changeExam', methods=['POST'])
def changeExam():
    exam = request.form['selectedExam']
    course = request.form['selectedCourse']
    return mkt_reader_writer.get_question_files(course, exam)

@app.route('/getFolders', methods=['POST'])
def getFolders():
    course = request.form['course']
    return mkt_reader_writer.get_folders(course)

@app.route('/getQuestions', methods=['POST'])
def getQuestions():
    course = request.form['course'].strip()
    fileName = request.form['file'].strip()
    questions = mkt_reader_writer.load_questions_file(course, fileName)
    return json.dumps(questions)


@app.route('/addItem', methods=['POST'])
def addQuestion():
    course = request.form['course']
    exam = request.form['exam']
    item = request.form['item']
    path = request.form['path']
    name = request.form['name']

    if (item == 'question'):
        #add question
        # TODO
        return
    elif (item == 'file'):
        #add category
        return mkt_reader_writer.create_category(name, course, path)
    elif (item == 'folder'):
        #add section
        return mkt_reader_writer.create_section(name, course, path)
    
    raise Exception

# @app.route('/uploadQuestions', methods=['POST'])
# def uploadQuestions():
#     questionFile = request.files['file']
#     return mkt_reader_writer.read_question_file(questionFile)

if __name__ == '__main__':
    app.run(debug=True)