#!/usr/bin/env python

import os, sys, argparse
import sqlite3
from random import random
import ConfigParser

class MKT:
   path = ''
   test = 'No test defined in ini file'
   instructor = 'No instructor defined in ini file'
   term = 'No term'
   of = None
   cur = None
   courseName = None
   courseNumber = None
   dapartment = None
   school = None
   points = 2

   def __init__( self, configFile, outfile ):
      config = ConfigParser.RawConfigParser(allow_no_value=True)
      config.optionxform=str
      config.read(configFile)
      self.path = config.get("config", "path")
      self.test = config.get("config", "test")
      self.instructor = config.get("config", "instructor")
      self.courseName = config.get("config", "courseName")
      self.courseNumber = config.get("config", "courseNumber")
      self.term = config.get("config", "term")
      self.school = config.get("config", "school")
      self.department = config.get("config", "department")


      # TODO: Do not overwrite by default
      if not os.path.isdir(self.path):
         fatal("%s: directory does not exist" % (selfpath ))
      self.of = open(outfile, 'w')

      self.writeHeader()
      fileList = self.getQuestions()
      ( m, n ) = self.readQuestions( fileList )
      self.generateTest( m, n )
      self.writeFooter()


   def writeHeader( self ):
      # TODO: only print out answer if it was asked for
      print >> self.of, "\documentclass[11pt,answers, addpoints]{exam}\n"
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

   def getQuestions(self):
      for parent, ldirs, lfiles in os.walk(self.path ):
         lfiles   = [nm for nm in lfiles if not nm.startswith('.')]
         ldirs[:] = [nm for nm in ldirs  if not nm.startswith('.')]  # in place
         lfiles.sort()
         for nm in lfiles:
            nm = os.path.join(parent, nm)
            yield nm

   def shuffle(self, items):  # returns new list
      return [t[1] for t in sorted((random(), i) for i in items)]

         
   def readQuestions(self, fileList):
      shortAnswerQuestions = []
      multipleChoiceQuestions = []

      # randomize the list of questions
      fileList = self.shuffle( fileList )
      
      for q in fileList:
         # TODO: Read file and import it into the correct list
         config = ConfigParser.RawConfigParser(allow_no_value=True)
         config.optionxform=str
         config.read(q)
         if config.get("config", "type") == "shortAnswer":
            shortAnswerQuestions.append( config )
         elif config.get("config", "type" ) == "multipleChoice":
            multipleChoiceQuestions.append( config )

      return ( shortAnswerQuestions, multipleChoiceQuestions )


   def generateTest( self, shortAnswer, multipleChoice ):
      # Reorder the questions
      shortAnswer = self.shuffle( shortAnswer )

      # print out the short answer questions. TODO: Print header here
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
         if m.has_option( "config", "points" ):
            points = m.getint( "config", "points" )

         self.of.write("\\question[%d]\n" % points )

         # Write out the question
         for a in m.options("question"):
            self.of.write("%s\n" % (a))

         self.of.write("\\begin{solution}[%sin]\n" % ( "0" ))
        
         # Write out the solution
         for a in m.options("solution"):
            self.of.write("%s\n" % (a))

         self.of.write("\\end{solution}\n\n")

      print >> self.of, "\\endgradingrange{shortanswer}"
      print >> self.of, "\\newpage"


      # Print multiple choice questions: TODO print out the header
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
         self.of.write("\\question[%d]\n" % (self.points))
         for a in m.options("question"):
            self.of.write("%s\n" % (a))

         answers = self.shuffle( m.items("answers"))
         self.of.write("\\begin{checkboxes}\n")
         for a,b in answers:
            if b == None:
               self.of.write("\\choice %s\n" % ( a ))
            else:
               self.of.write("\\CorrectChoice %s\n" % ( b ))
         self.of.write("\\end{checkboxes}\n\n\n")

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
   parser.add_argument("-a", "--answerKey", help="Generate answer key")
   args = parser.parse_args()
   # TODO: add answer key support
   configFile = args.configFile;
   outfile = args.ofile;
   
   mkt = MKT( configFile, outfile )
      

if __name__ == '__main__':
   main( sys.argv );

