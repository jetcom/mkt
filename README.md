mkt is a program design to read test questions from 1 or more files and
generate written exams.  The config files can specify the maximum number of
points for a group of questions, or the maximum number of questions to pick
from a set.  This makes it possible to have n different ways to ask a
questions, and leaving it up to mkt to pick one at random.  

mkt outputs files in LaTeX format and will optionally generate pdf files from
the tex file.  

By default, a corresponding answer key is generated for the supplied test.

mkt supports the following types of questions:

* long answer - at least one sentence for the answer
* short answer - typically one word answers
* multiple choice
* matching
* true/false

The example folder provides samples of how mkt can be used. To run mkt with
these samples, run:

   ./mkt example/sample.ini 

Optional arguments include:
optional arguments:

  -h, --help            show this help message and exit

  -f, --force           Force overwriting of outfile, if it exists

  -d DEST, --dest DEST  Destination for output

  -r, --draft           Adds a draft watermark, makes the exam ID larger

  -n, --noAnswerKey     do NOT generate corresponding answer key

  -p, --pdf             Generate pdf for test and key files
  
  -q, --quiz            Generates a file with no cover page or section headers (quiz mode)

  -t, --test            Ignore limits on number of points and questions.
                        Useful for testing

  -u UUID, --uuid UUID  Generate a test with the specific UUID

  -v VERSIONS, --versions VERSIONS
                        Generate multiple versions of this exam

  --version             show program's version number and exit
