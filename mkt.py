#!/usr/bin/env python

import os, sys, argparse
import sqlite3
from random import random
#import ConfigParser
from configobj import ConfigObj

class MKT:
   test = None
   instructor = None
   term = None
   of = None
   cur = None
   courseName = None
   courseNumber = None
   dapartment = None
   school = None
   solutionSpace = '3in'
   answerKey = ''
   points = 2

   def __init__( self, configFile, outfile, answerKey, force ):
      questions = []
      path = os.path.dirname( configFile )

      config = ConfigObj(configFile)

      self.test = config["config"]["test"]
      self.instructor = config["config"]["instructor"]
      self.courseName = config["config"]["courseName"]
      self.courseNumber = config["config"]["courseNumber"]
      self.term = config["config"]["term"]
      self.school = config["config"]["school"]
      self.department = config["config"]["department"]
      if 'solutionSpace' in config["config"]:
         self.solutionSpace = config["config"]["solutionSpace"]

      if answerKey == True: 
         self.answerKey = "answers,"

      for s in config.iterkeys():
         if s != "config":
            p = "%s/%s" % (path, s)
            if os.path.isdir(p):
               files = self.getQuestions(p)
            elif os.path.isfile(p):
               files = [p]
            else:
               fatal("%s: directory or file does not exist" % (p))

            q = self.readQuestions(files)
            q = self.shuffle(q);

            # Check to see if there is a config set to limit the number of
            # questions in this section.  If so, retrieve it and cut the 
            # list down
            if 'questions' in config[s]:
               q = q[:int(config[s]["questions"])]
            questions+=q

      if not force and os.path.exists(outfile):
         fatal("%s: file already exists" % ( outfile ))
      self.of = open(outfile, 'w')

      self.writeHeader()
      self.generateTest( questions )
      self.writeFooter()


   def writeHeader( self ):
      # TODO: only print out answer if it was asked for
      print >> self.of, "\documentclass[11pt,%s addpoints]{exam}\n" % (self.answerKey)
      print >> self.of, "\usepackage{amssymb}\n" \
                        "\usepackage{graphicx}\n" \
                        "\usepackage{color}\n\n"

      print >> self.of, "\pagestyle{headandfoot}"

      print >> self.of, "\\firstpageheader{%s} {} { Name: \makebox[2in]{\hrulefill}}" % ( self.test )
      print >> self.of, "\\runningheader{%s} {} { Name: \makebox[2in]{\hrulefill}}" % ( self.test)
      print >> self.of, "\\firstpagefooter{%s} {Page \\thepage\ of \\numpages} {\makebox[.5in]{\hrulefill}/\pointsonpage{\\thepage}}" % (self.courseNumber )
      print >> self.of, "\\runningfooter{%s} {Page \\thepage\ of \\numpages} {\makebox[.5in]{\hrulefill}/\pointsonpage{\\thepage}}" % ( self.courseNumber )

      print >> self.of, "\n"
      print >> self.of, "\\checkboxchar{$\\Box$}"
      print >> self.of, "\\CorrectChoiceEmphasis{\color{red}}"
      print >> self.of, "\\SolutionEmphasis{\color{red}}"
      print >> self.of, "\\renewcommand{\questionshook}{\setlength{\itemsep}{.35in}}"
      print >> self.of, "\\bonuspointpoints{bonus point}{bonus points}"

      print >> self.of, "\n"

      print >> self.of, "\\begin{document}"
      print >> self.of, "\\begin{coverpages}"
      print >> self.of, "\\begin{center}"
      print >> self.of, "\\vspace*{1in}"

      print >> self.of, "\n"

      print >> self.of, "\\textsc{\LARGE %s \\\\%s }\\\\[1.5cm]" % ( self.school, self.department )  
      print >> self.of, "\\textsc{\LARGE %s}\\\\[1cm]" % ( self.courseName )
      print >> self.of, "\\textsc{\LARGE %s}\\\\[2cm]" % ( self.term )
      print >> self.of, "\\textsc{\Huge %s}" % ( self.test )
      print >> self.of, "\\vfill"

      print >> self.of, "\n"
      print >> self.of, "{\Large { Score: \makebox[1in]{\hrulefill} / \\numpoints }} \\\\[4cm]" 
      print >> self.of, "\end{center}"
      print >> self.of, "\makebox[\\textwidth]{Name: \enspace\hrulefill}"
      print >> self.of, "\end{coverpages}"

      print >> self.of, "\n"


   def writeFooter( self ):
      print >> self.of, "\end{questions}"
      print >> self.of, "\end{document}"

   def getQuestions(self, path):
      for parent, ldirs, lfiles in os.walk( path ):
         lfiles   = [nm for nm in lfiles if not nm.startswith('.')]
         ldirs[:] = [nm for nm in ldirs  if not nm.startswith('.')]  # in place
         lfiles.sort()
         for nm in lfiles:
            nm = os.path.join(parent, nm)
            yield nm

   def shuffle(self, items):  # returns new list
      return [t[1] for t in sorted((random(), i) for i in items)]

         
   def readQuestions(self, fileList):
      rval = []

      for f in fileList:
         maxQuestions = None
         qList = []

         print "%s..." % (f)
         config = ConfigObj( f )
         for c in config:
            if c == "config":
               if "questions" in config[c]:
                  maxQuestions = int(config["config"]["questions"])
            else:
               qList.append( config[c] )

         print "\tFound %d question%s" % (len(qList), 's' if len(qList)>1 else '')
         # Pick a number of questions
         if maxQuestions:
            print "\tLimiting to %d question%s" % (maxQuestions, 's' if maxQuestions>1 else '')
            qList = self.shuffle(qList)
            qList = qList[:maxQuestions]

         print "\tAdding %d question%s" % (len(qList), 's' if len(qList)>1 else '')
         rval += qList

      return ( rval )


   def generateTest( self, questions ):
      shortAnswer = []
      multipleChoice = []
      bonusQuestions = []

      for q in questions:
         # We don't care about the section name.. Just get the first one
         # (there should only ever be one!)
         if "bonus" in q and q["bonus"].lower() == "true":
            if q["type"] != "multipleChoice":
               fatal("Only multiple choice bonus questions are currently supported")
            bonusQuestions.append(q)
         elif q["type"] == "shortAnswer":
            shortAnswer.append( q )
         elif q["type"] == "multipleChoice":
            multipleChoice.append( q )

      # Reorder the questions
      if len(shortAnswer) > 0:
         shortAnswer = self.shuffle( shortAnswer )

         # print out the short answer questions. 
         print >> self.of, "\\begin{center}"
         print >> self.of, "{\Large \\textbf{Short Answers Questions}}"
         print >> self.of, "\\fbox{\\fbox{\\parbox{5.5in}{\centering"
         print >> self.of, "Answer the questions in the spaces provided on the question sheets."
         print >> self.of, "If you run out of room for an answer, continue on the back of the page."
         print >> self.of, "}}}"
         print >> self.of, "\end{center}\n"

         print >> self.of, "\\begin{questions}"
         print >> self.of, "\\begingradingrange{shortanswer}"

         for m in shortAnswer:
            points = self.points;
            if 'points' in m:
               points = int(m["points"])

            self.of.write("\\begin{minipage}[b]{\\linewidth} % Keep the following lines together\n")
            self.of.write("\\question[%d]\n" % points )

            # Write out the question
            self.of.write("%s\n" % (m["question"]))

            solutionSpace = self.solutionSpace
            if 'solutionSpace' in m:
               solutionSpace = m["solutionSpace"]
            self.of.write("\\begin{solution}[%s]\n" % ( solutionSpace ))
         
            # Write out the solution
            self.of.write("%s\n" % (m["solution"]))

            self.of.write("\\end{solution}\n")
            self.of.write("\\end{minipage}\n\n")

         print >> self.of, "\\endgradingrange{shortanswer}"

         print >> self.of, "\\newpage"


      count = 0
      if len(multipleChoice) > 0 or len(bonusQuestions)>0:
         # Print multiple choice questions: 
         print >> self.of, "\\begin{center}"
         print >> self.of, "{\Large \\textbf{Multiple Choice Questions}}"
         print >> self.of, "\\fbox{\\fbox{\\parbox{5.5in}{\centering"
         print >> self.of, "Mark the box the represents the \textit{best} answer.  If you make an"
         print >> self.of, "incorrect mark, erase your mark and clearly mark the correct answer."
         print >> self.of, "If the intended mark is not clear, you will receive a 0 for that question"
         print >> self.of, "}}}"
         print >> self.of, "\end{center}\n"


         multipleChoice = self.shuffle( multipleChoice )
         for m in multipleChoice:
            points = self.points;
            if 'points' in m:
               points = int(m["points"])

            self.of.write("\\question[%d]\n" % (points))
            self.of.write("%s\n" % (m["question"]))

            answers = {m["correctAnswer"]:"CorrectChoice"}
            answers.update({v:"choice" for v in m["wrongAnswers"]})
            answers = self.shuffle(answers.items())

            self.of.write("\\begin{checkboxes}\n")
            for a,b in answers:
               self.of.write("\\%s %s\n" % (b, a ) )
            self.of.write("\\end{checkboxes}\n\n\n")

            count = count + 1
            if count % 4 == 0:
               self.of.write("\\pagebreak\n\n")


         for m in self.shuffle(bonusQuestions):
            points = self.points;
            if 'points' in m:
               points = int(m["points"])
            self.of.write("\\bonusquestion[%d]\n" % (points))
            self.of.write("%s\n" % (m["question"]))

            answers = {m["correctAnswer"]:"CorrectChoice"}
            answers.update({v:"choice" for v in m["wrongAnswers"]})
            answers = self.shuffle(answers.items())

            self.of.write("\\begin{checkboxes}\n")
            for a,b in answers:
               self.of.write("\\%s %s\n" % (b, a ) )
            self.of.write("\\end{checkboxes}\n\n\n")

            count = count + 1
            if count % 4 == 0:
               self.of.write("\\pagebreak\n\n")

         print >> self.of, "\\endgradingrange{multiplechoice}"




def fatal( str ):
   print >> sys.stderr, str
   sys.exit(2)


def main( argv ):
   path = '';
   outfile = '';

   parser = argparse.ArgumentParser()
   parser.add_argument("configFile", help="Config file for this exam" )
   parser.add_argument("ofile", help="Destination .tex file" )
   parser.add_argument("-a", "--answerKey", help="Generate answer key", action='store_true')
   parser.add_argument("-f", "--force", help="Force overwriting of outfile, if it exists", action='store_true')
   args = parser.parse_args()
   configFile = args.configFile;
   outfile = args.ofile;
   
   mkt = MKT( configFile, outfile, args.answerKey, args.force )
      

if __name__ == '__main__':
   main( sys.argv );

