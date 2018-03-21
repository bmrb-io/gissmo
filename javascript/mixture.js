$( "form" ).submit(function( event ) {
    console.log($( this ).serializeObject());

var serialized = $( this ).serializeJSON();
  event.preventDefault();

    $.ajax({
        type: "POST",
        url: "",
        // The key needs to match your method's input parameter (case-sensitive).
        data: serialized,
        contentType: "application/json; charset=utf-8",
        //dataType: "json",
        success: function(data){$("#results").html(data);},
        failure: function(errMsg) {
            alert(errMsg);
        }
    });

});

function parseCSV(csvArray){
    var compound_pos = csvArray[0].indexOf('Compound Name');
    var concentration_pos = csvArray[0].indexOf('Concentration (mM)');

    for (var i=1; i<csvArray.length; i++){
        if (csvArray[i][concentration_pos]){
            console.log("Found compound with name " + csvArray[i][compound_pos]);
        }
    }
}

function openFile() {
    var input = document.getElementById("experiment_file");
    var reader = new FileReader();
    reader.onload = function(){
        parseCSV($.csv.toArrays(reader.result));
    }
    reader.readAsText(input.files[0]);
}

function addCompound() {
    var compound = $("#compound_new").val();
    var id = $("#id_new").val();
    if (!compound){
        alert("Please select a compound from one of the suggestions that will appear as you type.");
        return null;
    }
    var concentration = $("#concentration_new").val();
    var reference = $("#reference_new").is(':checked');

    var row = $("<tr></tr>");
    var control = $("<td></td>").append($('<input type="button" value="Delete">').bind('click', { row: row }, function(event) { event.data.row.remove();}));
    compound = $("<td></td>").append($('<input type="text" name="mixture[][compound]" readonly="true">').val(compound))
                             .append($('<input type="hidden" name="mixture[][id]">').val(id));
    concentration = $("<td></td>").append($('<input type="text" name="mixture[][concentration]">').val(concentration));
    reference = $("<td></td>").append($('<input type="checkbox" name="mixture[][reference]">').prop('checked', reference));
    row.append(control, compound, concentration, reference).insertBefore("#compound_anchor");

    // Reset the values
    $("#compound_new").val('');
    $("#concentration_new").val('');
    $("#reference_new").prop('checked', false);
}

function escape_regexp(text) {
  return text.replace(/[-[\]{}()*+?.,\\^$|#\s]/g, "\\$&");
}

$.expr[':'].textEquals = function (a, i, m) {
  return $(a).text().match("^" + escape_regexp(m[3]) + "$");
};


$( "#compound_new" ).autocomplete({
    minLength: 2,
    delay: 0,
    source: function(request, response) {
        $.getJSON("http://webapi.bmrb.wisc.edu/v2/instant", { database: "metabolomics", term : request.term },
        response);
    },
    change: function (event, ui) {
        if(!ui.item){
            //http://api.jqueryui.com/autocomplete/#event-change -
            // The item selected from the menu, if any. Otherwise the property is null
            //so clear the item for force selection
            $("#compound_new").val("");
        }

    }, select: function(event, ui) {
        $("#id_new").val(ui.item.value);
        $("#compound_new").val(ui.item.label);
        return false;
    }
}).data("ui-autocomplete")._renderItem = function (ul, item) {
     return add_color_span_instant(ul, item, "compound_new");
};

// Use this to highlight the query words in a given text
function highlight_words(words, text){
    regex = new RegExp("(" + words.join("|") + ")", "ig");
    return text.replace(regex, '<strong>$1</strong>');
}

function add_color_span_instant(ul, item, id) {

    var terms = document.getElementById(id).value.split(/[ ,]+/);
    var display = highlight_words(terms, item.value + ": " + item.label);

    var hidden_div = $('<div style="display: none" class="instant_search_extras"></div>');

    // Only show authors or citations if there are any...
    if (item.authors.length > 0){
        hidden_div.append($("<span><b>BMRB ID</b>: " + item.inchi + "</span><br>"));
    }

    if ("extra" in item){
        hidden_div.append($("<span><b>" + item.extra.termname + "</b>: " + highlight_words(terms, item.extra.term) + "</span><br>"));
    }

    return $("<li></li>")
        .mouseenter(function(e){ hidden_div.show(0); })
        .mouseleave(function(e){ hidden_div.hide(0); })
        .data("item.autocomplete", item)
        .append("<a><span style='cursor:pointer;'>" + display + "</span></a>").append(hidden_div)
        .appendTo(ul);
}
