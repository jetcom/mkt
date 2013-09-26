#!/usr/bin/env python

import os, sys, argparse
import tempfile
import shutil
import subprocess
import random
import uuid
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

   # Enable test mode
   testMode = False

   ###########################################
   # __init__
   ##########################################
   def __init__( self, args ):

      answerKey = not args.noAnswerKey
      
      # List of questions
      questions = []

      # Name of the file for the answer key
      answerFilename = ''

      # output file pointer
      of = None

      # keyfile points
      kf = None

      # Initialize RNG
      if not args.uuid:
         args.uuid = uuid.uuid1()
         print "New UUID: %s" % args.uuid
      random.seed(args.uuid)

      self.testMode = args.test

      if self.testMode:
         print ">>> TEST MODE ENABLED <<<"

      fileName, fileExtension = os.path.splitext(args.outfile)

      answerFilename = fileName + ".key.tex"

      if not fileExtension.lower() == ".tex":
         args.outfile+=".tex"

      path = os.path.dirname( args.configFile )

      if not args.force and os.path.exists(args.outfile):
         fatal("%s: file already exists" % ( args.outfile ))
      of = open(args.outfile, 'w')

      if answerKey and not args.force and os.path.exists(answerFilename):
         fatal("%s: file already exists" % ( answerFilename ))
      kf = open(answerFilename, 'w')

      # Read in the ini file specified on the command line
      print "Reading %s" % ( args.configFile )


      config = ConfigObj(args.configFile)
      questions = self.parseConfig( 'File', args.configFile, config, root=path)



      # Generate the test onec
      tempFile = tempfile.TemporaryFile()
      self.generateTest( tempFile, questions )

      self.writeHeader( of, '', args )

      # Now we write copy from the temp file to the test file
      tempFile.seek(0,0)
      shutil.copyfileobj( tempFile, of )

      self.writeFooter( of )
      print("\nTest file written: %s" % (args.outfile))

      if answerKey:
         self.writeHeader( kf, answerKey, args )

         # Write the same test contents
         tempFile.seek(0,0)
         shutil.copyfileobj( tempFile, kf )

         self.writeFooter( kf )
         print("Answer key file written: %s" % ( answerFilename ))

      of.close()
      kf.close()
      tempFile.close()


      if args.pdf:
         self.createPDF( args.outfile, answerFilename )

      print ""
      print "If you have the same config file and question set, you can regenerate"
      print "this test with by specifing the following argument to mkt:"
      print "\t-u %s" % args.uuid
      print ""

   ##########################################
   # createPDF
   ##########################################
   def createPDF( self, outFile, answerFilename ):
      print("Generating PDFs...")
      fileName, fileExtension = os.path.splitext(outFile)
      oldpath = os.getcwd()
      newpath = os.path.dirname(outFile)
      logFile = open("%s.log" % (fileName), "w" )

      if len(newpath) == 0:
         newpath = "."

      executable = ["pdflatex", "-halt-on-error", outFile]
      for i in range(0,3):
         process = subprocess.Popen( executable, stdout=subprocess.PIPE)
         for line in process.stdout:
            logFile.write(line)
         if process.wait() != 0:
            logFile.close()
            os.chdir(oldpath)
            fatal("Error running pdflatex. Check logs.")

      if len(answerFilename) > 0:
         executable = ["pdflatex", "-halt-on-error", answerFilename ]
         for i in range(0,3):
            process = subprocess.Popen( executable, stdout=subprocess.PIPE)
            for line in process.stdout:
               logFile.write(line)
            if process.wait() != 0:
               logFile.close()
               os.chdir(oldpath)
               fatal("Error running pdflatex. Check logs.")

      logFile.close();
      os.chdir(oldpath)


   ##########################################
   # writeHeader
   ##########################################
   def writeHeader( self, of, answerKey, args ):
      print >> of, "% This document generated with mkt"
      print >> of, "%%       uuid: %s" % args.uuid
      print >> of, "%% configFile: %s" % args.configFile
      if answerKey:
         print >> of, "\documentclass[11pt,answers,addpoints]{exam}\n"
      else:
         print >> of, "\documentclass[11pt,addpoints]{exam}\n" 

      print >> of, "\usepackage{amssymb}\n" \
                        "\usepackage{graphicx}\n" \
                        "\usepackage{listings}\n" \
                        "\usepackage{color}\n\n"

      print >> of, "\pagestyle{headandfoot}"

      if answerKey:
         print >> of, "\\firstpageheader{%s} {} { \\textcolor{red}{KEY} }" % ( self.config["test"] )
         print >> of, "\\runningheader{%s} {} { \\textcolor{red}{KEY} }" % ( self.config["test"])
      else:
         if "nameOnEveryPage" in self.config and self.config["nameOnEveryPage"].lower() == "true":
            print >> of, "\\firstpageheader{%s} {} { Name: \makebox[2in]{\hrulefill}}" % ( self.config["test"] )
            print >> of, "\\runningheader{%s} {} { Name: \makebox[2in]{\hrulefill}}" % ( self.config["test"])
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
      if answerKey:
         print >> of, "{\Large { Score: \makebox[1in]{\underline{\hspace{5mm}\\textcolor{red}{KEY} \hspace{5mm}}} / \\numpoints }} \\\\[4cm]" 
      else:
         print >> of, "{\Large { Score: \makebox[1in]{\hrulefill} / \\numpoints }} \\\\[4cm]" 

      print >> of, "\end{center}"
      if answerKey:
         print >> of, "\makebox[\\textwidth]{\\textcolor{red}{KEY}}"
      else:
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
      if self.testMode:
         return items
      else:
         return [t[1] for t in sorted((random.random(), i) for i in items)]

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
      if c in [ "test", "instructor",  "courseName", "courseNumber", "term",
            "school", "department", "nameOnEveryPage", "defaultPoints",
            "defaultSolutionSpace", "useCheckboxes", "defaultLineLength" ]: 
         if not  self.mainSettingsStored:
            self.mainSettingsStored = True
            self.config = config

            # Set up some defaults of the keys aren't found
            if "useCheckboxes" not in self.config:
               self.config["useCheckboxes"] = "false"

            if "defaultLineLength" not in self.config:
               self.config["defaultLineLength"] = "1in"

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

         # If it's a long answer question, make sure there is a solution
         # space defined
         if "type" not in config:
            fatal("'type' not defined for question")

         if config["type"].lower() == "longanswer" and not "solutionSpace" in config:
            if self.defaultSolutionSpace:
               config["solutionSpace"] = self.defaultSolutionSpace
            else:
               fatal("'solutionSpace' and 'defaultSolutionSpace' cannot both be undefined for short answer questions")

         # Append the question to the question List
         config["key"] = name
         qList.append(config)

      else: # Not a question
         print "%s: '%s' - Parsing" % ( descriptor, name )
         # No questions at this level.  Need to recursive look for them
         for c in config:
            if c == "maxQuestions":
               if not self.testMode:
                  maxQuestions = int(config[c])
            elif c == "maxPoints":
               if not self.testMode:
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
   # createMultipleChoiceQuestions
   ##########################################
   def createMultipleChoiceQuestions( self, of, questions, bonus = None ):
      for m in self.shuffle( questions ):
         self.beginMinipage( of )
         if bonus: 
            of.write("\\bonusquestion[%d]\n" % (int(m["points"])))
         else:
            of.write("\\question[%d]\n" % int(m["points"]))

         of.write("%s\n" % (m["question"]))
         of.write("\\medskip\n")

         try:
            answers = {m["correctAnswer"]:"CorrectChoice"}
         except TypeError:
            fatal("correctAnswer not defined for %s" % (m))
         try:
            answers.update({v:"choice" for v in m["wrongAnswers"]})
         except KeyError:
            fatal("'wrongAnswers' not defined for %s" % (m))
         answers = self.shuffle(answers.items())

         if self.config["useCheckboxes"].lower() == "true":
            of.write("\\begin{checkboxes}\n")
            for a,b in answers:
               of.write("\\%s %s\n" % (b, a ) )
            of.write("\\end{checkboxes}\n\n\n")
         else:
            of.write("\\begin{choices}\n")
            currentAnswer = 'A'
            for a,b in answers:
               of.write("\\%s %s\n" % ( "choice", a ))
               if b == "CorrectChoice" :
                  correctAnswer = currentAnswer
               currentAnswer = chr(ord(currentAnswer)+1)

            if "lineLength" in m:
               lineLength = m["lineLength"]
            else:
               lineLength = self.config["defaultLineLength"]

            of.write("\\end{choices}\n")
            
            # Answer lines for multiple choice questions are always 1in
            of.write("\\setlength\\answerlinelength{1in}\n") 
            of.write("\\answerline[%s]\n\n" % ( correctAnswer ))
         self.endMinipage( of )

      

   ###########################################
   # generateTest
   ##########################################
   def generateTest( self, of, questions ):
      longAnswer = []
      shortAnswer = []
      multipleChoice = []
      bonusQuestions = []

      for q in questions:
         try:
            if "bonus" in q and q["bonus"].lower() == "true":
               if q["type"].lower() != "multiplechoice":
                  fatal("Only multiple choice bonus questions are currently supported")
               bonusQuestions.append(q)
            elif q["type"].lower() == "longanswer":
               longAnswer.append( q )
            elif q["type"].lower() == "multiplechoice":
               multipleChoice.append( q )
            elif q["type"].lower() == "shortanswer":
               shortAnswer.append( q )
            else:
               fatal("unknown test type: %s" % (q["type"]))
         except KeyError:
            fatal("'type' not defined: %s" % ( q ))

      # 
      # START: Short Answer Questions
      #
      if len(longAnswer) > 0:
         # print out the short answer questions. 
         print >> of, "\\begin{center}"
         print >> of, "{\Large \\textbf{Long Answers Questions}}"
         print >> of, "\\fbox{\\fbox{\\parbox{5.5in}{\centering"
         print >> of, "Answer the questions in the spaces provided on the question sheets."
         print >> of, "If you run out of room for an answer, continue on the back of the page."
         print >> of, "}}}"
         print >> of, "\end{center}\n"

         print >> of, "\\begin{questions}"
         print >> of, "\\begingradingrange{longanswer}"

         for m in self.shuffle(longAnswer):

            #print ">>>>>>>>>>>>>>>>>>>"
            #print m
            #print ">>>>>>>>>>>>>>>>>>>"
            #print m.parent
            #print ">>>>>>>>>>>>>>>>>>>"
            #sys.exit(0)
            self.beginMinipage( of );

            of.write("\\question[%d]\n" % int(m["points"]))
            of.write("%s\n" % (m["question"]))

            # Write out the solution
            of.write("\\begin{solution}[%s]\n" % ( m["solutionSpace"] ))
            of.write("%s\n" % (m["solution"]))
            of.write("\\end{solution}\n")

            self.endMinipage( of )


         print >> of, "\\endgradingrange{longanswer}"
         print >> of, "\\newpage"


      #
      # START: Short answer questions
      #
      if len( shortAnswer) > 0 :
         if self.config["useCheckboxes"].lower() == "true":
            print "#########################################################"
            print "# Multiple choice checkboxes not recommended when using  "
            print "# short answer questions.  Unset useCheckboxes in your "
            print "# config file to remove this warning."
            print "#########################################################"
         print >> of, "\\begin{center}"
         print >> of, "{\Large \\textbf{Short Answer Choice Questions}}"
         print >> of, "\\fbox{\\fbox{\\parbox{5.5in}{\centering"
         print >> of, "Write the correct answer in the space provided next to the question."
         print >> of, "Answer that are not legible or not made in the space provided will result in a 0 for that question."

         print >> of, "}}}"
         print >> of, "\end{center}\n"
         print >> of, "\\begingradingrange{shortAnswer}"

         for m in self.shuffle( shortAnswer ):
            self.beginMinipage( of );

            of.write("\\question[%d]\n" % int(m["points"]))
            of.write("%s\n" % (m["question"]))

            # Write out the solution
            if "lineLength" in m:
               lineLength = m["lineLength"]
            else:
               lineLength = self.config["defaultLineLength"]
            of.write("\\setlength\\answerlinelength{%s}\n" % ( lineLength ))
            

            # Since "solutions" is more correct for a multiple answer
            # questions, also allow that
            if "solutions" in m:
               if "solution" in m:
                  fatal("'solution' and 'solutions' cannot be defined for the same question.\nQuestion: \"%s\"" % m["question"] )
               else:
                  m["solution"] = m["solutions"]

            # If solution wasn't defined, error out
            if "solution" not in m:
               fatal("No 'solution' found!\nQuestion: \"%s\"\nKeys found: %s" % (m["question"] , (m.keys())))


            # If we have more than one solution, print out each on it's own
            # answer line
            if isinstance ( m["solution"], str ):
               of.write("\\answerline[%s]\n" % m["solution"])
            else:
               for s in m["solution"]:
                  of.write("\\answerline[%s]\n" % s)


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
         if self.config["useCheckboxes"].lower() == "true":
            print >> of, "Mark the box the represents the \\textit{best} answer.  If you make an"
            print >> of, "incorrect mark, erase your mark and clearly mark the correct answer."
            print >> of, "If the intended mark is not clear, you will receive a 0 for that question"
         else:
            print >> of, "Write the \\textit{best} answer in the space provided next to the question."
            print >> of, "Answer that are not legible or not made in the space provided will result in a 0 for that question."

         print >> of, "}}}"
         print >> of, "\end{center}\n"
         print >> of, "\\begingradingrange{multipleChoice}"


         #
         # START: Regular multiple choice questions
         #
         self.createMultipleChoiceQuestions( of, multipleChoice )

         #
         # START: Bonus multiple choice questions
         #
         self.createMultipleChoiceQuestions( of, bonusQuestions, True )

         print >> of, "\\endgradingrange{multiplechoice}"




def fatal( str ):
   print >> sys.stderr, "\nFATAL ERROR:"
   print >> sys.stderr, str
   sys.exit(2)


def main( argv ):
   path = '';
   outfile = '';

   parser = argparse.ArgumentParser()
   parser.add_argument("configFile", help="Config file for this exam" )
   parser.add_argument("outfile", help="Destination .tex file" )
   parser.add_argument("-f", "--force", help="Force overwriting of outfile, if it exists", action='store_true')
   parser.add_argument("-n", "--noAnswerKey", help="do NOT generate corresponding answer key", action='store_true')
   parser.add_argument("-p", "--pdf", help="Generate pdf for test and key files", action="store_true");
   parser.add_argument("-t", "--test", help="Ignore limits on number of points and questions. Useful for testing", action='store_true')

   parser.add_argument("-u", "--uuid", help="Generate a test with the specific UUID" )
   
   mkt = MKT( parser.parse_args() )
      

if __name__ == '__main__':
   main( sys.argv );

