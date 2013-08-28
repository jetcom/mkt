#!/usr/bin/env python

import os, sys, argparse
import tempfile
import shutil
from random import random
#import ConfigParser
from configobj import ConfigObj

class MKT:
   # set to True when the master settings are read. This is done so we only
   # have to do it once
   mainSettingsStored = False

   # config structure for the master settings
   config = None

   # default number of points for questions that don't have it set
   defaultPoints = 2

   # default space for the solution, for questions that don't have it set
   defaultSolutionSpace = None

   # current indent level
   indent = 0 

   ###########################################
   # __init__
   ##########################################
   def __init__( self, configFile, outfile, answerKey, force ):
      # List of questions
      questions = []

      # Name of the file for the answer key
      answerFilename = ''

      # output file pointer
      of = None

      # keyfile points
      kf = None


      fileName, fileExtension = os.path.splitext(outfile)

      answerFilename = fileName + ".key.tex"

      if not fileExtension.lower() == ".tex":
         outfile+=".tex"

      path = os.path.dirname( configFile )

      if not force and os.path.exists(outfile):
         fatal("%s: file already exists" % ( outfile ))
      of = open(outfile, 'w')

      if answerKey and not force and os.path.exists(outfile):
         fatal("%s: file already exists" % ( answerFilename ))
      kf = open(answerFilename, 'w')

      # Read in the ini file specified on the command line
      print "Reading %s" % ( configFile )
      config = ConfigObj(configFile)
      questions = self.parseConfig( 'File', configFile, config, root=path)



      # Generate the test onec
      tempFile = tempfile.TemporaryFile()
      self.generateTest( tempFile, questions )

      self.writeHeader( of, '' )

      # Now we write copy from the temp file to the test file
      tempFile.seek(0,0)
      shutil.copyfileobj( tempFile, of )

      self.writeFooter( of )
      print("\nTest file written: %s" % (outfile))



      if answerKey:
         self.writeHeader( kf, 'answers,' )

         # Write the same test contents
         tempFile.seek(0,0)
         shutil.copyfileobj( tempFile, kf )

         self.writeFooter( kf )
         print("Answer key file written: %s" % ( answerFilename ))

      of.close()
      kf.close()
      tempFile.close()

   ###########################################
   # writeHeader
   ##########################################
   def writeHeader( self, of, answerKey ):
      print >> of, "\documentclass[11pt,%s addpoints]{exam}\n" % (answerKey)
      print >> of, "\usepackage{amssymb}\n" \
                        "\usepackage{graphicx}\n" \
                        "\usepackage{color}\n\n"

      print >> of, "\pagestyle{headandfoot}"

      if ( "nameOnEveryPage" in self.config and self.config["nameOnEveryPage"].lower() == "true" ):
         print >> of, "\\firstpageheader{%s} {} { Name: \makebox[2in]{\hrulefill}}" % ( self.test )
         print >> of, "\\runningheader{%s} {} { Name: \makebox[2in]{\hrulefill}}" % ( self.test)
      else:
         print >> of, "\\firstpageheader{%s} {} {}" % ( self.config["test"] )
         print >> of, "\\runningheader{%s} {} {}" % ( self.config["test"] )


      print >> of, "\\firstpagefooter{%s} {Page \\thepage\ of \\numpages} {\makebox[.5in]{\hrulefill}/\pointsonpage{\\thepage}}" % (self.config["courseNumber"] )
      print >> of, "\\runningfooter{%s} {Page \\thepage\ of \\numpages} {\makebox[.5in]{\hrulefill}/\pointsonpage{\\thepage}}" % ( self.config["courseNumber"] )

      print >> of, "\n"
      print >> of, "\\checkboxchar{$\\Box$}"
      print >> of, "\\CorrectChoiceEmphasis{\color{red}}"
      print >> of, "\\SolutionEmphasis{\color{red}}"
      print >> of, "\\renewcommand{\questionshook}{\setlength{\itemsep}{.35in}}"
      print >> of, "\\bonuspointpoints{bonus point}{bonus points}"

      print >> of, "\n"

      print >> of, "\\begin{document}"
      print >> of, "\\begin{coverpages}"
      print >> of, "\\begin{center}"
      print >> of, "\\vspace*{1in}"

      print >> of, "\n"

      print >> of, "\\textsc{\LARGE %s \\\\%s }\\\\[1.5cm]" % ( self.config["school"], self.config["department"] )  
      print >> of, "\\textsc{\LARGE %s}\\\\[1cm]" % ( self.config["courseName"] )
      print >> of, "\\textsc{\LARGE %s}\\\\[2cm]" % ( self.config["term"] )
      print >> of, "\\textsc{\Huge %s}" % ( self.config["test"] )
      print >> of, "\\vfill"

      print >> of, "\n"
      print >> of, "{\Large { Score: \makebox[1in]{\hrulefill} / \\numpoints }} \\\\[4cm]" 
      print >> of, "\end{center}"
      print >> of, "\makebox[\\textwidth]{Name: \enspace\hrulefill}"
      print >> of, "\end{coverpages}"

      print >> of, "\n"


   ###########################################
   # writeFooter
   ##########################################
   def writeFooter( self, of ):
      print >> of, "\end{questions}"
      print >> of, "\end{document}"

   ###########################################
   # getQuestions
   ##########################################
   def getQuestions(self, path):
      for parent, ldirs, lfiles in os.walk( path ):
         lfiles   = [nm for nm in lfiles if not nm.startswith('.')]
         ldirs[:] = [nm for nm in ldirs  if not nm.startswith('.')]  # in place
         lfiles.sort()
         for nm in lfiles:
            nm = os.path.join(parent, nm)
            yield nm

   ###########################################
   # shuffle
   ##########################################
   def shuffle(self, items):  # returns new list
      return [t[1] for t in sorted((random(), i) for i in items)]

   ###########################################
   # processInclude
   ##########################################
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

   ###########################################
   # parseTestSettings
   ##########################################
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


         # We did consumer this key
         return True

      # We did NOT consume this key
      return False

   ###########################################
   # parseConfig
   ##########################################
   def parseConfig( self, descriptor, name, config, root=None ):
      sys.stdout.write("  "*self.indent)

      qList = []
      maxQuestions = None
      maxPoints = None
      showSummary = True

      # found a question. Add it!
      if "question" in config:
         print "%s: %s - Adding question" % ( descriptor, name )
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

      else: # Not a question
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



   ###########################################
   # beginMinipage
   ##########################################
   def beginMinipage( self, of ):
      of.write("\\par\\vspace{.5in}\\begin{minipage}{\\linewidth}\n")

   ###########################################
   # endMinipage
   ##########################################
   def endMinipage( self, of ):
      of.write("\\end{minipage}\n")
      of.write("\n\n")

   ###########################################
   # generateTest
   ##########################################
   def generateTest( self, of, questions ):
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

      # 
      # START: Short Answer Questions
      #
      if len(shortAnswer) > 0:
         shortAnswer = self.shuffle( shortAnswer )

         # print out the short answer questions. 
         print >> of, "\\begin{center}"
         print >> of, "{\Large \\textbf{Short Answers Questions}}"
         print >> of, "\\fbox{\\fbox{\\parbox{5.5in}{\centering"
         print >> of, "Answer the questions in the spaces provided on the question sheets."
         print >> of, "If you run out of room for an answer, continue on the back of the page."
         print >> of, "}}}"
         print >> of, "\end{center}\n"

         print >> of, "\\begin{questions}"
         print >> of, "\\begingradingrange{shortanswer}"

         for m in shortAnswer:
            self.beginMinipage( of );

            of.write("\\question[%d]\n" % int(m["points"]))
            of.write("%s\n" % (m["question"]))

            # Write out the solution
            of.write("\\begin{solution}[%s]\n" % ( m["solutionSpace"] ))
            of.write("%s\n" % (m["solution"]))
            of.write("\\end{solution}\n")

            self.endMinipage( of )


         print >> of, "\\endgradingrange{shortanswer}"
         print >> of, "\\newpage"


      # 
      # START: Multiple choice questions
      #
      if len(multipleChoice) > 0 or len(bonusQuestions)>0:
         # Print multiple choice questions: 
         print >> of, "\\begin{center}"
         print >> of, "{\Large \\textbf{Multiple Choice Questions}}"
         print >> of, "\\fbox{\\fbox{\\parbox{5.5in}{\centering"
         print >> of, "Mark the box the represents the \textit{best} answer.  If you make an"
         print >> of, "incorrect mark, erase your mark and clearly mark the correct answer."
         print >> of, "If the intended mark is not clear, you will receive a 0 for that question"
         print >> of, "}}}"
         print >> of, "\end{center}\n"


         #
         # START: Regular multiple choice questions
         #
         multipleChoice = self.shuffle( multipleChoice )
         for m in multipleChoice:
            self.beginMinipage( of )
            of.write("\\question[%d]\n" % int(m["points"]))
            of.write("%s\n" % (m["question"]))
            of.write("\\medskip\n")

            answers = {m["correctAnswer"]:"CorrectChoice"}
            try:
               answers.update({v:"choice" for v in m["wrongAnswers"]})
            except KeyError:
               fatal("'wrongAnswers' not defined for %s" % (m))
            answers = self.shuffle(answers.items())

            of.write("\\begin{checkboxes}\n")
            for a,b in answers:
               of.write("\\%s %s\n" % (b, a ) )
            of.write("\\end{checkboxes}\n\n\n")

            self.endMinipage( of )


         #
         # START: Bonus multiple choice questions
         #
         for m in self.shuffle(bonusQuestions):

            self.beginMinipage( of )
            of.write("\\bonusquestion[%d]\n" % (int(m["points"])))
            of.write("%s\n" % (m["question"]))
            of.write("\\medskip\n")

            answers = {m["correctAnswer"]:"CorrectChoice"}
            try:
               answers.update({v:"choice" for v in m["wrongAnswers"]})
            except KeyError:
               fatal("'wrongAnswers' not defined for %s" % (m))
            answers = self.shuffle(answers.items())

            of.write("\\begin{checkboxes}\n")
            for a,b in answers:
               of.write("\\%s %s\n" % (b, a ) )
            of.write("\\end{checkboxes}\n\n\n")
            self.endMinipage( of )

         print >> of, "\\endgradingrange{multiplechoice}"




def fatal( str ):
   print >> sys.stderr, str
   sys.exit(2)


def main( argv ):
   path = '';
   outfile = '';

   parser = argparse.ArgumentParser()
   parser.add_argument("configFile", help="Config file for this exam" )
   parser.add_argument("ofile", help="Destination .tex file" )
   parser.add_argument("-n", "--noAnswerKey", help="do NOT generate corresponding answer key", action='store_true')
   parser.add_argument("-f", "--force", help="Force overwriting of outfile, if it exists", action='store_true')
   args = parser.parse_args()
   configFile = args.configFile;
   outfile = args.ofile;
   
   mkt = MKT( configFile, outfile, not args.noAnswerKey, args.force )
      

if __name__ == '__main__':
   main( sys.argv );

