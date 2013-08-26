#!/usr/bin/env python

import os, sys, argparse
import sqlite3
from random import random
#import ConfigParser
from configobj import ConfigObj

class MKT:
   of = None
   answerKey = ''

   mainSettingsStored = False
   config = None

   defaultPoints = 2
   defaultSolutionSpace = None

   indent = 0 

   def __init__( self, configFile, outfile, answerKey, force ):
      questions = []
      path = os.path.dirname( configFile )

      if answerKey == True: 
         self.answerKey = "answers,"

      if not force and os.path.exists(outfile):
         fatal("%s: file already exists" % ( outfile ))
      self.of = open(outfile, 'w')

      print "Reading %s" % ( configFile )
      config = ConfigObj(configFile)



      questions = self.parseConfig( 'File', configFile, config, root=path)

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

      if ( "nameOnEveryPage" in self.config and self.config["nameOnEveryPage"].lower() == "true" ):
         print >> self.of, "\\firstpageheader{%s} {} { Name: \makebox[2in]{\hrulefill}}" % ( self.test )
         print >> self.of, "\\runningheader{%s} {} { Name: \makebox[2in]{\hrulefill}}" % ( self.test)
      else:
         print >> self.of, "\\firstpageheader{%s} {} {}" % ( self.config["test"] )
         print >> self.of, "\\runningheader{%s} {} {}" % ( self.config["test"] )


      print >> self.of, "\\firstpagefooter{%s} {Page \\thepage\ of \\numpages} {\makebox[.5in]{\hrulefill}/\pointsonpage{\\thepage}}" % (self.config["courseNumber"] )
      print >> self.of, "\\runningfooter{%s} {Page \\thepage\ of \\numpages} {\makebox[.5in]{\hrulefill}/\pointsonpage{\\thepage}}" % ( self.config["courseNumber"] )

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

      print >> self.of, "\\textsc{\LARGE %s \\\\%s }\\\\[1.5cm]" % ( self.config["school"], self.config["department"] )  
      print >> self.of, "\\textsc{\LARGE %s}\\\\[1cm]" % ( self.config["courseName"] )
      print >> self.of, "\\textsc{\LARGE %s}\\\\[2cm]" % ( self.config["term"] )
      print >> self.of, "\\textsc{\Huge %s}" % ( self.config["test"] )
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

   def processInclude( self, config, root=None ):
      rval = []
      # If there is only one thing in out list, make it a list so we can
      # reuse the same code below
      if isinstance ( config, str ):
         config = [config]
         
      for inc in config:
         self.indent+=1
         # If it's a directory, read all the files in the directory
         if root:
            inc = "%s/%s" % (root, inc)

         if os.path.isdir( inc ):
            files = self.getQuestions( inc )

         # If it's a file, read it in
         elif os.path.isfile( inc ):
            files = [inc]
         else:
            fatal("%s: directory or file does not exist" % (inc))

         for f in files:
            rval += self.parseConfig( 'File', f, ConfigObj( f, interpolation=True ))
         self.indent-=1
      return rval

   def parseTestSettings( self, c, config ):
      if c in [ "test", "instructor",  "courseName", "courseNumber", "term", "school", "department", "nameOnEveryPage", "defaultPoints", "defaultSolutionSpace" ]: 
         if not  self.mainSettingsStored:
            self.mainSettingsStored = True
            self.config = config

            # We need to do this once here because when we add questions, it
            # we want to add the default points settings. Everything else is
            # used on page genreation so it can be saved in the struct for
            # later
            if "defaultPoints" in config:
               self.defaultPoints = config["defaultPoints"]

            # Same for defaultSolutionSpace
            if "defaultSolutionSpace" in config:
               self.defaultSolutionSpace = config["defaultSolutionSpace"]


         return True

      return False

   def parseConfig( self, descriptor, name, config, root=None ):
      sys.stdout.write("  "*self.indent)

      qList = []
      maxQuestions = None
      maxPoints = None
      showSummary = True

      # found a question. Add it!
      if "question" in config:

         # If points is not set, set it here
         if not "points" in config:
            config["points"] = self.defaultPoints

         # If it's a short answer question, make sure there is a solution
         # space defined
         if config["type"].lower() == "shortanswer" and not "solutionSpace" in config:
            if self.defaultSolutionSpace:
               config["solutionSpace"] = self.defaultSolutionSpace
            else:
               fatal("'solutionSpace' and 'defaultSolutionSpace' cannot both be undefined for short answer questions")

         qList.append(config)
         print "%s: %s - Adding question" % ( descriptor, name )
      else:
         print "%s: '%s' - Parsing" % ( descriptor, name )
         # No questions at this level.  Need to recursive look for them
         for c in config:
            if c == "maxQuestions":
               maxQuestions = int(config[c])
            elif c == "maxPoints":
               maxPoints = int(config[c])
            elif c == "include":
               qList += self.processInclude( config["include"], root=root )
            elif self.parseTestSettings( c, config ):
               continue
            elif not isinstance (config[c], str ):
               self.indent+=1
               qList += self.parseConfig( 'Section',  c, config[c], root=root )
               self.indent-=1
            else:
               fatal("Unknown token: %s" % c )
      

      # Cut the list down to get the max points requested
      totalPoints = 0;
      for p in qList:
         totalPoints += int(p["points"])

      if maxPoints and totalPoints > maxPoints:
         showSummary = False
         qList = self.shuffle(qList)
         newList = []

         newPoints = 0
         for p in qList:
            if newPoints + int(p["points"]) <= maxPoints:
               newPoints += int(p["points"])
               newList.append(p)

         sys.stdout.write("  "*self.indent)
         print "%s: '%s': maxPoints set to %d" % ( descriptor, name, maxPoints) 
         sys.stdout.write("  "*self.indent)
         print "  old total: %d   old # of questions: %d" % ( totalPoints, len(qList ))
         sys.stdout.write("  "*self.indent)
         print "  new total: %d   new # of questions: %d" % ( newPoints, len(newList))

         qList = newList
         totalPoints = newPoints



      if maxQuestions and len(qList) > maxQuestions:
         showSummary = False
         qList = self.shuffle(qList)
         qList = qList[:maxQuestions]

         sys.stdout.write("  " * self.indent)
         print "%s: '%s': maxQuestions set to %d" % (descriptor, name, maxQuestions)

      # if we didn't already show a summary
      #   AND
      #     We are in a section with at least 2 elements
      #       OR
      #     We are a file
      if showSummary and ((len( qList ) > 1 and descriptor == 'Section') or
            descriptor == 'File'):
         sys.stdout.write("  " * self.indent )

         print "%s: '%s' - Adding %d questions worth %d points" % (descriptor,
               name, len(qList), totalPoints )

      return qList



   def beginMinipage( self ):
      self.of.write("\\par\\vspace{.5in}\\begin{minipage}{\\linewidth}\n")

   def endMinipage( self ):
      self.of.write("\\end{minipage}\n")
      self.of.write("\n\n")

   def generateTest( self, questions ):
      shortAnswer = []
      multipleChoice = []
      bonusQuestions = []

      for q in questions:
         try:
            if "bonus" in q and q["bonus"].lower() == "true":
               if q["type"].lower() != "multiplechoice":
                  fatal("Only multiple choice bonus questions are currently supported")
               bonusQuestions.append(q)
            elif q["type"].lower() == "shortanswer":
               shortAnswer.append( q )
            elif q["type"].lower() == "multiplechoice":
               multipleChoice.append( q )
            else:
               fatal("unknown test type: %s" % (q["type"]))
         except KeyError:
            fatal("'type' not defined: %s" % ( q ))

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
            self.beginMinipage();

            self.of.write("\\question[%d]\n" % int(m["points"]))
            self.of.write("%s\n" % (m["question"]))

            # Write out the solution
            self.of.write("\\begin{solution}[%s]\n" % ( m["solutionSpace"] ))
            self.of.write("%s\n" % (m["solution"]))
            self.of.write("\\end{solution}\n")

            self.endMinipage()


         print >> self.of, "\\endgradingrange{shortanswer}"
         print >> self.of, "\\newpage"


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
            self.beginMinipage()
            self.of.write("\\question[%d]\n" % int(m["points"]))
            self.of.write("%s\n" % (m["question"]))
            self.of.write("\\medskip\n")

            answers = {m["correctAnswer"]:"CorrectChoice"}
            try:
               answers.update({v:"choice" for v in m["wrongAnswers"]})
            except KeyError:
               fatal("'wrongAnswers' not defined for %s" % (m))
            answers = self.shuffle(answers.items())

            self.of.write("\\begin{checkboxes}\n")
            for a,b in answers:
               self.of.write("\\%s %s\n" % (b, a ) )
            self.of.write("\\end{checkboxes}\n\n\n")

            self.endMinipage()


         for m in self.shuffle(bonusQuestions):

            self.beginMinipage()
            self.of.write("\\bonusquestion[%d]\n" % (int(m["points"])))
            self.of.write("%s\n" % (m["question"]))
            self.of.write("\\medskip\n")

            answers = {m["correctAnswer"]:"CorrectChoice"}
            try:
               answers.update({v:"choice" for v in m["wrongAnswers"]})
            except KeyError:
               fatal("'wrongAnswers' not defined for %s" % (m))
            answers = self.shuffle(answers.items())

            self.of.write("\\begin{checkboxes}\n")
            for a,b in answers:
               self.of.write("\\%s %s\n" % (b, a ) )
            self.of.write("\\end{checkboxes}\n\n\n")
            self.endMinipage()

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

