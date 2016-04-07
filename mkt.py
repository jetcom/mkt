#!/usr/bin/env python

import os, sys, argparse, errno
import tempfile
import shutil
import subprocess
import random
import uuid
import hashlib
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

   # Enable draft mode
   draftMode = False

   # Total points is used for maxPercent calculations
   totalPoints = None

   # For maxPercent to work, we need to make two passes. This will be set to
   # true if we encounter a maxPercent keyword
   needSecondPass = False
   currentPass = 1


   # hash used for duplicate question detection. Since we want to keep track
   # of ALL questions, regardless of whether we use it in a test or not, we
   # can make it a member variable
   qHash = {}

   ###########################################
   # __init__
   ##########################################
   def __init__( self, args ):

      # If the user specifies 1 versions, it's the same as none specified
      if not args.versions:
         pass
      elif args.versions < 1:
         fatal("-v <#> must be 1, or greater")
      elif args.versions > 10:
         fatal("-v <#> must be 10, or less")

      if args.versions == 1:
         args.versions = None

      try:
         with open ( args.configFile ): pass
      except IOError:
         fatal("Could not open %s" % (args.configFile ))

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

      self.draftMode = args.draft 


      # Read in the ini file specified on the command line
      print "Reading %s" % ( args.configFile )

      path = os.path.dirname( args.configFile )

      config = ConfigObj(args.configFile)
      questions = self.parseConfig( 'File', args.configFile, config, root=path)

      if self.needSecondPass:
         self.currentPass = 2
         self.qHash = {}
         self.totalPoints = 0
         for q in questions:
            self.totalPoints += int(q["points"])
         print("-------------------------------------------------------")
         print("Encounted maxPercent.. reparsing.")
         print("Total points: %d" % ( self.totalPoints ))
         print("-------------------------------------------------------")

         # Reseed with the same UUID so we get the same questionsList
         random.seed(args.uuid)
         questions = self.parseConfig( 'File', args.configFile, config, root=path)

      if args.versions:
         for v in range( 0, int(args.versions) ):
            self.writeTest( args, questions, chr(v+ord('A') ))
      else:
         self.writeTest( args, questions )





      print ""
      print "If you have the same config file and question set, you can regenerate"
      print "this test with by specifing the following argument to mkt:"
      print "\t-u %s" % args.uuid
      print ""



   ##########################################
   # writeTest
   ##########################################
   def writeTest( self, args, questions, version = None ):
      # invert this so it makes it easy to use
      answerKey = not args.noAnswerKey


      fileName, fileExtension = os.path.splitext(args.configFile)
      baseName = os.path.basename( fileName )

      if args.dest:
         destDir = args.dest + "/"
      else:
         destDir = fileName + "/"


      try:
         os.makedirs( destDir, 0700 )
      except OSError as e:
         if e.errno == errno.EEXIST and os.path.isdir(destDir):
            pass
         else:
            fatal("Can not create destination direction %s" % (destDir))




      if version:
         baseName += "." + version

      outFilename = destDir + baseName + ".tex"
      answerFilename = destDir + baseName + ".key.tex"

      # Check if the files exist
      if not args.force and os.path.exists( outFilename):
         fatal("%s: file already exists" % ( outFilename ))
      of = open(outFilename, 'w')

      if answerKey:
         if not args.force and os.path.exists(answerFilename):
            fatal("%s: file already exists" % ( answerFilename ))
         kf = open(answerFilename, 'w')

      # Generate the test once
      tempFile = tempfile.TemporaryFile()
      self.generateTest( tempFile, questions )

      self.writeHeader( of, '', args, version )

      # Now we write copy from the temp file to the test file
      tempFile.seek(0,0)
      shutil.copyfileobj( tempFile, of )

      self.writeFooter( of )
      print("\nTest file written: %s" % ( outFilename ))

      if answerKey:
         self.writeHeader( kf, 'answers,', args, version )

         # Write the same test contents
         tempFile.seek(0,0)
         shutil.copyfileobj( tempFile, kf )

         self.writeFooter( kf )
         print("Answer key file written: %s" % ( answerFilename ))

      of.close()
      kf.close()
      tempFile.close()

      if args.pdf:
         self.createPDF( outFilename, answerFilename )

   ##########################################
   # createPDF
   ##########################################
   def createPDF( self, outFile, answerFilename ):
      # TODO: This could stand to be reworked. It's ugly
      print("Generating PDFs...")
      fileName, fileExtension = os.path.splitext(outFile)
      oldpath = os.getcwd()
      newpath = os.path.dirname(outFile)
      os.chdir( newpath )
      logFile = open("%s.log" % (os.path.basename(fileName)), "w" )

      if len(newpath) == 0:
         newpath = "."

      executable = ["pdflatex", "-halt-on-error", os.path.basename(outFile) ]
      for i in range(0,3):
         process = subprocess.Popen( executable, stdout=subprocess.PIPE)
         for line in process.stdout:
            logFile.write(line)
         if process.wait() != 0:
            logFile.close()
            os.chdir(oldpath)
            fatal("Error running pdflatex. Check logs.")

      if len(answerFilename) > 0:
         executable = ["pdflatex", "-halt-on-error", os.path.basename(answerFilename) ]
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
   def writeHeader( self, of, answerKey, args, version ):
      print >> of, "% This document generated with mkt"
      print >> of, "%%       uuid: %s" % args.uuid
      print >> of, "%% configFile: %s" % args.configFile
      if version:
         print >> of, "%%    version: %s" % version

      if answerKey:
         print >> of, "\documentclass[10pt,answers,addpoints]{exam}\n"
      else:
         print >> of, "\documentclass[10pt,addpoints]{exam}\n"

      print >> of, "\usepackage{amssymb}\n" \
                        "\usepackage{graphicx}\n" \
                        "\usepackage{listings}\n" \
                        "\usepackage{tabularx}\n" \
                        "\usepackage{color}\n\n"
      if args.draft:
          print >> of, "\usepackage{draftwatermark}\n"
          print >> of, "\SetWatermarkText{DRAFT}\n"
          print >> of, "\SetWatermarkScale{7}\n"

      print >> of, "\makeatletter"
      print >> of, "\ifcase \@ptsize \\relax % 10pt"
      print >> of, "\\newcommand{\miniscule}{\@setfontsize\miniscule{4}{5}}% \\tiny: 5/6"
      print >> of, "\or% 11pt"
      print >> of, "\\newcommand{\miniscule}{\@setfontsize\miniscule{5}{6}}% \\tiny: 6/7"
      print >> of, "\or% 12pt"
      print >> of, "\\newcommand{\miniscule}{\@setfontsize\miniscule{5}{6}}% \\tiny: 6/7"
      print >> of, "\\fi"
      print >> of, "\makeatother"
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
      print >> of, "\\textsc{\LARGE %s}\\\\[1cm]" % ( self.config["term"] )
      print >> of, self.config["instructor"] 
      print >> of, "\\textsc{\Huge %s}" % ( self.config["test"] )
      if version:
         print >> of, "\\\\[1cm]\\textsc{\LARGE Version: %s}" % ( version )

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
         if "promptForLogin" in self.config and self.config["promptForLogin"].lower() == "true":
            print >> of, "\makebox[0.60\\textwidth]{Name: \enspace\hrulefill}"
            print >> of, "\makebox[0.40\\textwidth]{DCE Login: \enspace\hrulefill}"

         else:
            print >> of, "\makebox[\\textwidth]{Name: \enspace\hrulefill}"

      print >> of, "\covercfoot{\\miniscule{ Exam ID: %s}}" % args.uuid
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
      if type(items) is dict:
         fatal("Cannot shuffle dictionaries")
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
            "defaultSolutionSpace", "useCheckboxes", "defaultLineLength",
            "promptForLogin" ]:
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
      maxPercent = None
      showSummary = True

      # found a question. Add it!
      if "question" in config:
         print "%s: %s - Adding question" % ( descriptor, os.path.basename(name) )

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

         # Check for dupes.  Strip out all whitespace in the string and
         # then get an md5 hash.  It's less to store and fairly quick to
         # compute
         s = "".join(config["question"].split())
         m = hashlib.md5(s).hexdigest()

         if m in self.qHash:
            print >> sys.stderr, "\nFATAL ERROR!! Duplication questions detected!"
            print >> sys.stderr, "   Question: \"%s\"" % config["question"]
            print >> sys.stderr, "   Initially processed in '%s'" % ( self.qHash[m] )
            print >> sys.stderr, "   Also processed in '%s'" % (name)
            sys.exit(2)
         else:
            self.qHash[m] = name
            # Append the question to the question List
            config["key"] = name
            qList.append(config)

      else: # Not a question
         print "%s: '%s' - Parsing" % ( descriptor, os.path.basename(name) )
         # No questions at this level.  Need to recursive look for them
         for c in config:
            if c.lower() == "maxquestions":
               if not self.testMode:
                  maxQuestions = int(config[c])
            elif c.lower() == "maxpoints":
               if not self.testMode:
                  maxPoints = int(config[c])
            elif c.lower() == "maxpercent":
                  maxPercent = int(config[c])
                  self.needSecondPass = True
            elif c == "include":
               qList += self.processInclude( config["include"], root=root )
            elif self.parseTestSettings( c, config ):
               continue
            elif not isinstance (config[c], str ):
               self.indent+=1
               try:
                  qList += self.parseConfig( 'Section', "%s/%s" % (name, c), config[c], root=root )
               except Exception as e:
                  print(e)
                  print("Section %s/%s" % (name, c))
                  sys.exit(0)

               self.indent-=1
            else:
               fatal("Unknown token: %s" % c )

      # This is needed to correctly fetch maxPoints and maxQuestions from the
      # "config" section of the ini file
      if "config" in config and "maxPoints" in config["config"]:
         maxPoints = (int)(config["config"]["maxPoints"])
      if "config" in config and "maxQuestions" in config["config"]:
         maxQuestions = (int)(config["config"]["maxQuestions"])


      if maxPoints and maxPercent:
         fatal("maxPoints and maxPercent cannot be specified for the same section!")

      # Cut the list down to get the max points requested
      sectionPoints = 0;
      for p in qList:
         sectionPoints += int(p["points"])

      if maxPoints and sectionPoints > maxPoints:
         showSummary = False
         qList = self.shuffle(qList)
         newList = []

         newPoints = 0

         for p in qList:
            if newPoints + int(p["points"]) <= maxPoints:
               newPoints += int(p["points"])
               newList.append(p)

         sys.stdout.write("  "*self.indent)
         print "%s: '%s': maxPoints set to %d" % ( descriptor, os.path.basename(name), maxPoints)
         sys.stdout.write("  "*self.indent)
         print "  old total: %d   old # of questions: %d" % ( sectionPoints, len(qList ))
         sys.stdout.write("  "*self.indent)
         print "  new total: %d   new # of questions: %d" % ( newPoints, len(newList))

         qList = newList
         sectionPoints = newPoints



      if maxQuestions and len(qList) > maxQuestions:
         showSummary = False
         qList = self.shuffle(qList)
         qList = qList[:maxQuestions]

         sys.stdout.write("  " * self.indent)
         print "%s: '%s': maxQuestions set to %d" % (descriptor, os.path.basename(name), maxQuestions)



      # Cut the list down to get the maxPercent requested.  This should happen
      # after maxQuestions since it's possible maxQuestions was used to pick 1
      # of 3 identical type questions.

      if self.totalPoints and maxPercent: # if we didn't get through the first pass yet, this won't work

         percentPoints = (int)(maxPercent/100.0 * self.totalPoints)
         if sectionPoints >= percentPoints:
            showSummary = False
            qList = self.shuffle(qList)
            newList = []

            # In this case, we want to get one MORE question than what is
            # required for maxPoints since we are just going for rough
            # percentages
            newPoints = 0
            for p in qList:
               newPoints += int(p["points"])
               newList.append(p)
               if newPoints > percentPoints:
                  break

            sys.stdout.write("  "*self.indent)
            print " %s: '%s': maxPercent set to %d%%" % ( descriptor, os.path.basename(name), maxPercent)
            sys.stdout.write("  "*self.indent)
            print "  old total: %d   old # of questions: %d" % ( sectionPoints, len(qList ))
            sys.stdout.write("  "*self.indent)
            print "  new total: %d   new # of questions: %d" % ( newPoints, len(newList))
            sys.stdout.write("  "*self.indent)
            print "  actual percentage: %d%%" % ( newPoints*100/self.totalPoints )

            qList = newList
            sectionPoints = newPoints
         else:
            sys.stdout.write("  "*self.indent)
            print " !! %s: '%s': maxPercent set to %d" % (descriptor, os.path.basename(name), maxPercent )
            sys.stdout.write("  "*self.indent)
            print " !!  We required at least %d points to meet this requirement, " % ( percentPoints )
            sys.stdout.write("  "*self.indent)
            print " !!  but only %d points were available." % ( sectionPoints )
            sys.stdout.write("  "*self.indent)
            print " !!  actual percentage: %d%%" % ( sectionPoints*100/self.totalPoints )


      # if we didn't already show a summary
      #   AND
      #     We are in a section with at least 2 elements
      #       OR
      #     We are a file
      if showSummary and ((len( qList ) > 1 and descriptor == 'Section') or
            descriptor == 'File'):
         sys.stdout.write("  " * self.indent )

         print "%s: '%s' - Adding %d questions worth %d points" % (descriptor,
               os.path.basename(name), len(qList), sectionPoints )

      return qList



   ###########################################
   # beginMinipage
   ##########################################
   def beginMinipage( self, of ):
      if self.config["useCheckboxes"].lower() == "true":
         space = .25
      else:
         space = .10
      of.write("\\par\\vspace{%fin}\\begin{minipage}{\\linewidth}\n" % (space))

   ###########################################
   # endMinipage
   ##########################################
   def endMinipage( self, of ):
      of.write("\\end{minipage}\n")
      of.write("\n\n")

   ###########################################
   # createTrueFalseQuestions
   ##########################################
   def createTrueFalseQuestions( self, of, questions, bonus = None ):
      for m in self.shuffle( questions ):
         self.beginMinipage( of )
         if bonus:
            of.write("\\bonusquestion[%d]\n" % (int(m["points"])))
         else:
            of.write("\\question[%d]\n" % int(m["points"]))

         if self.config["useCheckboxes"].lower() == "true":
            of.write("\ifprintanswers\n")
            if m["solution"].lower() == "true":
               of.write("\\textbf{[ \\textcolor{red}{True} / False ]} ")
            else:
               of.write("\\textbf{[ True / \\textcolor{red}{False} ]} ")
            of.write("\\else\n")
            of.write("\\textbf{[ True / False ]} ")
            of.write("\\fi\n")
            of.write("%s\n" % (m["question"]))
         else:
            if m["solution"].lower() == "true":
               correctAnswer = "True"
            else:
               correctAnswer = "False"
            of.write("%s\n" % (m["question"]))
            of.write("\\setlength\\answerlinelength{1in}\n")
            of.write("\\answerline[%s]\n\n" % ( correctAnswer ))

         of.write("\\medskip\n")
         self.endMinipage( of )

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
   # createShortAnswerQuestions
   ##########################################
   def createShortAnswerQuestions( self, of, questions, bonus = None ):
      for m in self.shuffle( questions ):
         self.beginMinipage( of );

         of.write("\\vspace{.35cm}")
         if bonus:
            of.write("\\bonusquestion[%d]\n" % (int(m["points"])))
         else:
            of.write("\\question[%d]\n" % int(m["points"]))

         of.write("%s\n" % (m["question"]))
         of.write("\\vspace{.25cm}")

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
               del m["solutions"]

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



   ###########################################
   # generateTest
   ##########################################
   def generateTest( self, of, questions ):
      longAnswer = []
      shortAnswer = []
      multipleChoice = []
      matching = []
      tf = []

      multipleChoiceBonus = []
      shortAnswerBonus = []

      beginQuestions = False

      for q in questions:
         try:
            # Handle bonus questions
            if "bonus" in q and q["bonus"].lower() == "true":
               if q["type"].lower() == "multiplechoice":
                  multipleChoiceBonus.append(q)
               elif q["type"].lower() == "shortanswer":
                  shortAnswerBonus.append(q)
               else:
                  fatal("Only multiple choice and short answer bonus questions are currently supported")



            elif q["type"].lower() == "longanswer":
               longAnswer.append( q )
            elif q["type"].lower() == "multiplechoice":
               multipleChoice.append( q )
            elif q["type"].lower() == "shortanswer":
               shortAnswer.append( q )
            elif q["type"].lower() == "matching":
               matching.append( q )
            elif q["type"].lower() == "tf":
               tf.append( q )
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
         beginQuestions=True

         for m in self.shuffle(longAnswer):

            self.beginMinipage( of );

            of.write("\\question[%d]\n" % int(m["points"]))
            of.write("%s\n" % (m["question"]))

            # Write out the solution
            of.write("\\begin{solution}[%s]\n" % ( m["solutionSpace"] ))
            of.write("%s\n" % (m["solution"]))
            of.write("\\end{solution}\n")

            self.endMinipage( of )


         print >> of, "\\endgradingrange{longanswer}\n\n\n"


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
         print >> of, "\\newpage"
         print >> of, "\\begin{center}"
         print >> of, "{\Large \\textbf{Short Answer Questions}}"
         print >> of, "\\fbox{\\fbox{\\parbox{5.5in}{\centering"
         print >> of, "Write the correct answer in the space provided next to the question."
         print >> of, "Answers that are not legible or not made in the space provided will result in a 0 for that question."
         print >> of, "}}}"
         print >> of, "\end{center}\n"
         if not beginQuestions:
            print >> of, "\\begin{questions}"
            beginQuestions = True
         print >> of, "\\begingradingrange{shortAnswer}"

         self.createShortAnswerQuestions( of, shortAnswer )

         print >> of, "\\endgradingrange{shortanswer}\n\n\n"

      #
      # START: T/F questions
      #
      if len( tf ) > 0:
         print >> of, "\\newpage"
         print >> of, "\\begin{center}"
         print >> of, "{\Large \\textbf{True/False Questions}}"
         print >> of, "\\fbox{\\fbox{\\parbox{5.5in}{\centering"
         if self.config["useCheckboxes"].lower() == "true":
            print >> of, "Circle either 'True' or 'False' at the begging of the line. If you make an"
            print >> of, "incorrect mark, erase your mark and clearly mark the correct answer."
            print >> of, "If the intended mark is not clear, you will receive a 0 for that question"
         else:
            print >> of, "Write 'True' or 'False' \\textit{clearly} in the space provided next to the question."
            print >> of, "Answer that are not legible or not made in the space provided will result in a 0 for that question."

         print >> of, "}}}"
         print >> of, "\end{center}\n"
         if not beginQuestions:
            print >> of, "\\begin{questions}"
            beginQuestions = True
         print >> of, "\\begingradingrange{TF}"
         self.createTrueFalseQuestions( of, tf )
         print >> of, "\\endgradingrange{TF}"


      #
      # START: Matching questions
      #
      if len(matching) > 0:
         print >> of, "\\newpage"
         print >> of, "\\begin{center}"
         print >> of, "{\Large \\textbf{Matching Questions}}"
         print >> of, "\\fbox{\\fbox{\\parbox{5.5in}{\centering"
         print >> of, "Match the selection on the left with the best answer on the right."
         print >> of, "Answers that are not legible or not made in the space provided will result in a 0 for that question."
         print >> of, "}}}"
         print >> of, "\end{center}\n"
         if not beginQuestions:
            print >> of, "\\begin{questions}"
            beginQuestions = True
         print >> of, "\\begingradingrange{matching}"

         for m in self.shuffle(matching):
            self.beginMinipage( of )
            of.write("\\question[%d]\n" % int(m["points"]))
            of.write("%s\\\\\n" % (m["question"]))
            of.write("\\def\\arraystretch{1.5}\n")
            of.write("\\medskip\n")
            of.write("\\begin{tabularx}{\\textwidth}{ X r X }\n")

            letter = 0
            solutions = {}
            for s in m["solutions"]:
               solutions[s] = chr(letter+ord('A'))
               letter += 1

            keys = self.shuffle(solutions.keys())

            index = 0
            for k in keys:
               of.write("%s. %s &\n" % (chr(index+ord('A')), m["choices"][index] ))
               of.write("\ifprintanswers\n")
               of.write("\\underline{\\hspace{.25cm}\\textcolor{red}{%s}\\hspace{.25cm}}\n" % (solutions[k]))
               of.write("\\else\n")
               of.write("\\underline{\\hspace{1cm}}")
               of.write("\\fi\n")
               of.write("& %s\n" % k )
               of.write("\\\\\n")
               index += 1



            of.write("\\end{tabularx}\n")
            self.endMinipage( of )


         print >> of, "\\endgradingrange{matching}\n\n\n"

      #
      # START: Multiple choice questions
      #
      if len(multipleChoice) > 0:
         # Print multiple choice questions:
         print >> of, "\\newpage"
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
         if not beginQuestions:
            print >> of, "\\begin{questions}"
            beginQuestions = True
         print >> of, "\\begingradingrange{multipleChoice}"


         #
         # START: Regular multiple choice questions
         #
         self.createMultipleChoiceQuestions( of, multipleChoice )
         print >> of, "\\endgradingrange{multiplechoice}\n\n\n"

      #
      # START: Bonus questions
      #
      if len( multipleChoiceBonus)>0 or len( shortAnswerBonus )> 0:
         print >> of, "\\newpage"
         print >> of, "\\begin{center}"
         print >> of, "{\Large \\textbf{Bonus Questions}}"
         print >> of, "\end{center}\n"
         if not beginQuestions:
            print >> of, "\\begin{questions}"
            beginQuestions = True
         print >> of, "\\begingradingrange{bonus}"

         self.createMultipleChoiceQuestions( of, multipleChoiceBonus, True )
         self.createShortAnswerQuestions( of, shortAnswerBonus, True )

         print >> of, "\\endgradingrange{multiplechoice}\n\n\n"




def fatal( str ):
   print >> sys.stderr, "\nFATAL ERROR!!"
   print >> sys.stderr, str
   sys.exit(2)


def main( argv ):
   path = '';
   outfile = '';

   parser = argparse.ArgumentParser()
   parser.add_argument("configFile", help="Config file for this exam" )
   parser.add_argument("-f", "--force", help="Force overwriting of outfile, if it exists", action='store_true')
   parser.add_argument("-d", "--dest", help="Destination for output" )
   parser.add_argument("-r", "--draft", help="Add a draft watermark", action='store_true')
   parser.add_argument("-n", "--noAnswerKey", help="do NOT generate corresponding answer key", action='store_true')
   parser.add_argument("-p", "--pdf", help="Generate pdf for test and key files", action="store_true");
   parser.add_argument("-t", "--test", help="Ignore limits on number of points and questions. Useful for testing", action='store_true')
   parser.add_argument("-u", "--uuid", help="Generate a test with the specific UUID" )
   parser.add_argument("-v", "--versions", help="Generate mulitple versions of this exam", type=int  )
   parser.add_argument("--version", action='version', version='%(prog)s 0.10')

   mkt = MKT( parser.parse_args() )


if __name__ == '__main__':
   main( sys.argv );

