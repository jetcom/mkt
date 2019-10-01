var course=""
var fileName = ""

$('#courseSelect').change(function() {
    $("#addQuestionButton").hide( );
    var optionSelected = $("select option:selected", this);
    var valueSelected = this.value;
    
    var data = "";
    $.ajax({
        type:"POST",
        url : "/changeCourse",
        data : {"selectedCourse": valueSelected},
        async: false,
        success : function(response) {
            data = response;
            return true;
    },
    error: function() {
  
    }
    });
    $("#questions").html("")
    $('#questionLabel').text("Select a question category from the left sidebar");
   
    var string = data.split(",");
    var array = string.filter(function(e){return e;});
    var select = $('#categorySelect');
    select.empty();
 
    $.each(array, function(index, value) { 
        value = value.trim();
        value = value.substr(0,value.length - 1)
        value = value.substr(1, value.length)
        select.append(
        $('<div class="w3-bar-item w3-button" onClick="fileClick(\''+value+'\')" id="'+value+'"></div>').html(value)
    );
    });
});


function fileClick(_fileName) {
    course = $('#courseSelect').find(":selected").text()
    fileName = _fileName
    $('#questionLabel').text(fileName);
    $('#addQuestionButton').show()


    w3_close()
    var data = "";
    $.ajax({
        type:"POST",
        url : "/getQuestions",
        data : {"course": course, "fileName": fileName},
        async: false,
        success : function(response) {
            data = response;
            return true;
    },
    error: function() {
  
    }
    });
    var questions = $.parseJSON(data)
    console.log(questions)
    $("#questions").html("")
    for (var title in questions) {
        question = questions[title]           
        $("#questions").append(formatQuestion("", title, question))
    }

    
}

function formatQuestion(parent, title, question) {

    output = '<div  class="w3-cell-row w3-block w3-light-grey ">'
    output += '<div onclick="accordion(\''+parent+title+'\')" class="w3-cell w3-btn w3-block w3-light-grey w3-left-align">'+title+'</div>'
    output += '<div onclick="alert(\'edit clicked\')" class="w3-btn w3-block w3-cell w3-right-align" >Edit</div>'
    output += '</div>'
    output += "<div id=\'"+parent+title+"\' class='w3-container w3-hide '>"

    if (question.type == null) 
    {
        output += "Max Questions: " + question.maxQuestions + '<br/>'
        for (var subtitle in question) {

            subquestion = question[subtitle]
             if (typeof subquestion === 'object') {
                output += formatQuestion(title, subtitle, subquestion)
            }
           
    }
    } else {
        output += "Type: " + question.type + "<br/>"
        if (question.points) {
            output += "Points: " + question.points + "<br/>"
        }
        output += "Question: " + question.question + "<br/>"
        if (question.solutionSpace)
        {
            output += "SolutionSpace: " + question.solutionSpace + "<br/>" 
        }
        switch (question.type.toLowerCase()) {
            case 'tf':
                output += "Solution: " + question.solution;
                break
            case 'shortanswer':
                if (question.solution) {
                    output += "Solution: " + question.solution;
                } 
                else {
                    output += "Solutions: " + question.solutions;
                }
                break
            case 'longanswer':
                output += "Solution: " + question.solution;
                break
            case 'multiplechoice':
                output += "Correct Solution: " + question.correctAnswer + "<br />"
                output += "Wrong Solutions: " + question.wrongAnswers
                break
        }

    }
    output += "</div>"
    return output
}

function w3_open() {
    document.getElementById("mySidebar").style.display = "block";
}

function w3_close() {
    document.getElementById("mySidebar").style.display = "none";
}

function accordion(id) {
    var x = document.getElementById(id);
    if (x.className.indexOf("w3-show") == -1) {
        x.className += " w3-show";
    } else { 
        x.className = x.className.replace(" w3-show", "");
    }
}

$('#newQuestion').submit(function(event){
    // cancels the form submission
    event.preventDefault();
    formData = $("#newQuestion").serialize()
    formData += "&filename="+fileName
    formData += "&course="+course
    console.log(formData)
    $.ajax({
        type:"POST",
        url : "/addQuestion",
        data : formData,
        async: false,
        success : function(response) {
            document.getElementById('addQuestionModal').style.display='none'
            fileClick(fileName)
            $("#newQuestion")[0].reset()
            return true;
        },
        error: function() {

        }
    });

});

$("#addQuestionButton").hide( );
