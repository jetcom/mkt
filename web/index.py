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
    return mkt_reader_writer.get_questions_files(course)
    

@app.route('/getQuestions', methods=['POST'])
def getQuestions():
    course = request.form['course'].strip()
    fileName = request.form['fileName'].strip()
    obj, questions = mkt_reader_writer.load_questions_file(course, fileName)
    return json.dumps(obj)


@app.route('/addQuestion', methods=['POST'])
def addQuestion():
    #course = request.form['course'].strip()
    #fileName = request.form['fileName'].strip()
    print(request.form)
    #obj, questions = mkt_reader_writer.load_questions_file("../questions/"+course+'/questionPool/'+fileName)
    return json.dumps(request.form)


@app.route('/uploadQuestions', methods=['POST'])
def uploadQuestions():
    questionFile = request.files['file']
    return mkt_reader_writer.read_question_file(questionFile)

if __name__ == '__main__':
    app.run(debug=True)