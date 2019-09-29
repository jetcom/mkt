from flask import Flask, escape, request, render_template
import mkt_reader_writer 
import os
import json



def get_immediate_subdirectories(a_dir):
    return [name for name in os.listdir(a_dir)
            if os.path.isdir(os.path.join(a_dir, name))]
courses = get_immediate_subdirectories('./')
print(courses)

app = Flask(__name__)

@app.route('/')
def home():
    #name = request.args.get("name", "World")
    #return f'Hello, {escape(name)}!'
    
    #obj, questions = mkt_reader_writer.load_questions_file("csci320 2191/questionPool/chapter1.txt")
    #print(questions)
    return render_template('home.html', courses=courses)


@app.route('/changeCourse', methods=['POST'])
def changeCourse():
    course = request.form['selectedCourse']
    print(course)

    files = os.listdir(course+'/questionPool')
    print(str(files))
    return str(files).strip('[]')
    

@app.route('/getQuestions', methods=['POST'])
def getQuestions():
    course = request.form['course'].strip()
    fileName = request.form['fileName'].strip()

    print(course+'/questionPool/'+fileName)
    obj, questions = mkt_reader_writer.load_questions_file(course+'/questionPool/'+fileName)
    print(questions)
    return json.dumps(questions)
    

if __name__ == '__main__':
    app.run(debug=True)