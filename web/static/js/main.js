
$('#courseSelect').change(function() {
    $('#examSelect').find('option').not(':first').remove();
    $('#examSelect').val($("#examSelect option:first").val());

    $.ajax({
        type: "POST",
        url: "/changeCourse",
        data: {"selectedCourse": this.value},
        async: false,
        success : function(response) {
            if (response){
                renderOptions($('#examSelect'), response)
            }
            return true;
        }
    });
});

$('#examSelect').change(function() {
    $('#explorer-body').empty();

    if (this.value) {
        var course = $('#courseSelect').val();

        $.ajax({
            type: "POST",
            url: "/changeExam",
            data: {
                "selectedExam": this.value,
                "selectedCourse": course,
            },
            async: false,
            success : function(response) {
                if (response) {
                    var arr = response.split(",");
                    arr.forEach(function(val, idx) {
                        val = val.trim();
                        renderQuestionsPath(val);
                        loadQuestions(course, val);
                    });
                }
                return true;
            }
        });
    }
});

$('#addCourseSelect').change(function() {
    $('#addExamSelect').empty();
    $.ajax({
        type: "POST",
        url: "/changeCourse",
        data: {"selectedCourse": this.value},
        async: false,
        success : function(response) {
            if (response){
                renderOptions($('#addExamSelect'), response)
            }
            return true;
        }
    });
});

// This may not be needed
// $('#addExamSelect').change(function() {
//     $('#addPathSelect').find('option').not(':first').remove();
//     $('#addPathSelect').val($("#examSelect option:first").val());

//     if (this.value) {
//         var course = $('#addCourseSelect').val();

//         $.ajax({
//             type: "POST",
//             url: "/changeExam",
//             data: {
//                 "selectedExam": this.value,
//                 "selectedCourse": course,
//             },
//             async: false,
//             success : function(response) {
//                 if (response) {
//                     renderOptions($('#addPathSelect'), response)
//                 }
//                 return true;
//             }
//         });
//     }
// });

$('#addItemSelect').change(function() {
    $('#addPathSelect').empty()
    
    var course = $('#addCourseSelect').val();
    var url = ""
    var data = {}

    if (this.value == 'file' || this.value == 'folder') {
        url = "/getFolders"
        data = { "course": course }
    } else {
        url = "/changeExam"
        data = {
            "selectedExam": this.value,
            "selectedCourse": course,
        }
    }

    $.ajax({
        type: "POST",
        url: url,
        data: data,
        async: false,
        success : function(response) {
            if (response) {
                renderOptions($('#addPathSelect'), response)
            }
            return true;
        }
    });
});

function renderOptions(target, response) {
    var arr = response.split(",");
    $.each(arr, function(idx, val) {
        val = val.trim();
        target.append(`<option value=${val}>${val}</option>`);
    });
}

function renderQuestionsPath(questions_path) {
    const path = questions_path.split('/');
    function element(item) { 
        return (`
            <ul id=${item}>
                <button id="${item}-button" value=${item} onclick="toggleFolder(this)" class="explorer-item-btn">
                    <i class="fa fa-folder-open explorer-icon" /> 
                    ${item}
                </button>
            </ul>
        `); 
    };

    path.forEach(function(item, idx) {
        target = $(`#${item}`);
        if (target.length != 0) {
            return;
        } else {
            if (idx == 0)  {
                target = $('#explorer-body');
            } else {
                target = $(`#${path[idx-1]}`)
            }
        }       
        target.append(element(item));
    });
}

function loadQuestions(course, questions_file) {
    $.ajax({
        type: "POST",
        url: "/getQuestions",
        data: {
            "course": course,
            "file": questions_file,
        },
        async: false,
        success : function(response) {
            const obj = JSON.parse(response);
            const path = questions_file.split('/');
            const id = path[path.length - 1];
            const target = $(`#${id}`);
            const buttons = Object.entries(obj).map(([name, question]) => {
                const button = $(`
                    <button class="explorer-item-btn">
                        <i class="fa fa-question-circle explorer-icon" /> ${name}
                    </button>
                `).wrap(`<li key=${name} class="question"></li>`).closest('li');
                button.click(() => {loadQuestion(path.splice(-1,1).join('/'), name, question)});
                return button
            });
            target.append(buttons);
        }
    });
}

function loadQuestion(path, name, question) {
    $('#question-prompt').hide();
    $('#question-name').text(`Question: ${name}`);

    const target = $('#question-container');

    // TODO
    // const questionHTML = formatQuestion(path, question);
    // target.empty();
    // target.append(questionHTML);
}

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

// TODO fix
function formatQuestion(path, question) {

    output = '<div>'
    output += '<div onclick="accordion(\''+path+'\')" class="w3-cell w3-btn w3-block w3-light-grey w3-left-align">'+path+'</div>'
    output += '<div onclick="alert(\'edit clicked\')" class="w3-btn w3-block w3-cell w3-right-align" >Edit</div>'
    output += '</div>'
    output += "<div id=\'"+path+"\' class='w3-container w3-hide '>"

    // if (question.type == null) 
    // {
    //     output += "Max Questions: " + question.maxQuestions + '<br/>'
    //     for (var subtitle in question) {

    //         subquestion = question[subtitle]
    //          if (typeof subquestion === 'object') {
    //             output += formatQuestion(title, subtitle, subquestion)
    //         }
           
    // }
    // } else {
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

    // }
    output += "</div>"
    return output
}

$('#addForm').submit(function(event){
    // cancels the form submission
    event.preventDefault();
    $('#addError').attr('hidden', 'hidden');

    formData = $("#addForm").serializeArray();
    $.ajax({
        type:"POST",
        url : "/addItem",
        data : formData,
        async: false,
        success : function(response) {
            $('#addModal').modal('hide');
            $('#addForm').trigger('reset');
            // refresh explorer
        },
        error: function() {
            $('#addError').removeAttr('hidden');
        }
    });
});

$('#fileSelectForm').submit(function(event) {
    event.preventDefault();

    var file = $('#file')[0].files[0];
    var formData = new FormData();
    formData.append('file', file);   

    $.ajax({
        type: "POST",
        url : "/uploadQuestions",
        data : formData,
        processData: false,
        contentType: false,
        success : function(response) {
            console.log(response)
            $('#fileModal').modal('hide');
        },
        error: function() {
            console.log('error')
        }
    })
});

$('#saveButton').on('click', function(){
    // $.ajax({
    //     type: "",
    //     url : "",
    //     data : ,
    //     processData: false,
    //     contentType: false,
    //     success : function(response) {

    //     },
    //     error: function() {
           
    //     }
    // })
});
