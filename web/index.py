from flask import Flask, escape, request, render_template
import mkt_reader_writer 
import os
import json


def get_immediate_subdirectories(a_dir):
    return [name for name in os.listdir(a_dir)
            if os.path.isdir(os.path.join(a_dir, name))]


courses = get_immediate_subdirectories('../questions/')
courses.sort()


app = Flask(__name__)

@app.route('/')
@app.route('/home')
def home():
    return render_template('home.html', courses=courses)

@app.route('/editor')
def editor():

    return render_template('editor.html', courses=courses)


@app.route('/changeCourse', methods=['POST'])
def changeCourse():
    course = request.form['selectedCourse']
    files = os.listdir("../questions/"+course+'/questionPool')
    files.sort()
    return str(files).strip('[]')
    

@app.route('/getQuestions', methods=['POST'])
def getQuestions():
    course = request.form['course'].strip()
    fileName = request.form['fileName'].strip()
    obj, questions = mkt_reader_writer.load_questions_file("../questions/"+course+'/questionPool/'+fileName)
    return json.dumps(obj)

@app.route('/addQuestion', methods=['POST'])
def addQuestion():
    #course = request.form['course'].strip()
    #fileName = request.form['fileName'].strip()
    print(request.form)
    #obj, questions = mkt_reader_writer.load_questions_file("../questions/"+course+'/questionPool/'+fileName)
    return json.dumps(request.form)


if __name__ == '__main__':
    app.run(debug=True)