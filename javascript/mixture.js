$( "form" ).submit(function( event ) {
    var serialized = $( this ).serializeJSON();
    event.preventDefault();

    $.ajax({
        type: "POST",
        url: "",
        // The key needs to match your method's input parameter (case-sensitive).
        data: serialized,
        contentType: "application/json; charset=utf-8",
        //dataType: "json",
        success: function(data){
            // Set the results div to what the server sends
            $("#results").html(data);
        },
        failure: function(errMsg) {
            alert(errMsg);
        }
    });

});


function addLoadedCompound(compound_name, concentration){

    // Skip compounds without concentration
    if ((!concentration) || (concentration === '--')){
        return;
    }

    // Query the API
    $.ajax({
        dataType: "json",
        url: "http://webapi.bmrb.wisc.edu/v2/instant",
        data: { database: "metabolomics", term : compound_name },
        beforeSend: function(request) {
            request.setRequestHeader("Application", 'GISSMO Mixtures');
        },
        success: function(compound_list) {
            var row = $("<tr></tr>").addClass('compound');
            var control = $("<td></td>").append($('<input type="button" value="Delete">').bind('click', { row: row }, function(event) { event.data.row.remove();}));
            var compound_id = $('<input type="text" readonly="true" name="mixture[][id]">');
            var compound_id_td = $("<td></td>").append(compound_id);
            var inchi = $('<input type="hidden" name="mixture[][inchi]">');

            var sel_td = $("<td><span>" + compound_name + ": </span></td>").addClass("left_align");

            var one_valid = false;
            var first = true;
            var sel = $("<select name='mixture[][compound]'>"); //.css('width', '100%');
            $(compound_list).each(function() {
                if (first){
                    compound_id.val(this.value);
                    inchi.val(this.inchi);
                    first = false;
                }
                if (valid_entries.indexOf(this.value) >= 0){
                    var option = $("<option>").attr('value', this.label).text(this.label + ' (' + this.value + ')').data('compound_id',this.value).data('inchi_string',this.inchi);
                    one_valid = true;
                    sel.append(option);
                }

            });
            sel.change(function () {
                compound_id.val($("option:selected", this).data('compound_id'));
                inchi.val($("option:selected", this).data('inchi_string'));
            });
            sel_td.append(sel);
            sel_td.append(inchi);

            // Insert error on no match
            if ((compound_list.length === 0) || (!one_valid)){
                var control_nomatch = $("<tr></tr>").addClass('compound').insertBefore("#compound_anchor");
                control_nomatch.append($('<td><input type="button" value="Delete"></td>').bind('click', { row: row }, function(event) { event.data.row.remove();}));
                control_nomatch.append($("<td>" + compound_name + "</td>").addClass('left_align'));
                control_nomatch.append($("<td></td>").html('No match'));
                control_nomatch.append($("<td></td>").html(concentration));
                control_nomatch.append($("<td></td>"));
                return;
            }

            var conc = $("<td></td>").append($('<input type="text" name="mixture[][concentration]">').val(concentration));
            var reference = $("<td></td>").append($('<input type="checkbox" name="mixture[][reference]">'));
            row.append(control, sel_td, compound_id_td, conc, reference).insertBefore("#compound_anchor");
      }
    });
}

function addCompound(selection) {
    if (!selection){
        alert("Please select a compound from one of the suggestions that will appear as you type.");
        return null;
    }

    var row = $("<tr></tr>").addClass('compound');
    var control = $("<td></td>").append($('<input type="button" value="Delete">').bind('click', { row: row }, function(event) { event.data.row.remove();}));
    var compound_td = $("<td></td>").addClass("left_align").append($('<input type="text" name="mixture[][compound]" readonly="true">').val(selection.label));
    var comp_id =  $("<td></td>").append($('<input type="text" name="mixture[][id]" readonly="true">').val(selection.value));
    var inchi = $('<input type="hidden" name="mixture[][inchi]">').val(selection.inchi);
    compound_td.append(inchi);
    var concentration = $("<td></td>").append($('<input type="text" name="mixture[][concentration]">'));
    var reference = $("<td></td>").append($('<input type="checkbox" name="mixture[][reference]">'));
    row.append(control, compound_td, comp_id, concentration, reference).insertBefore("#compound_anchor");

    // Reset the values
    $("#compound_search").val('');
}

function findLowercaseArray(item, array) {
    var lc_ray = array[0].map(function (x){return x.toLowerCase();});
    for (var i=0; i < lc_ray.length; i++){
        if (lc_ray[i].indexOf(item) >= 0){
            return i;
        }
    }
    return -1;
}

function parseCSV(csvArray){

    var compound_pos = findLowercaseArray('name', csvArray);
    var concentration_pos = findLowercaseArray('concentration', csvArray);

    if ((compound_pos < 0) || (concentration_pos < 0)){
        $("#message").html('The first row of the spreadsheet must have a column with the word "name" and a column with the word "concentration" in the cell in order to be properly detected.');
        return;
    }

    for (var i=1; i<csvArray.length; i++){
        if (csvArray[i][concentration_pos]){
            addLoadedCompound(csvArray[i][compound_pos], csvArray[i][concentration_pos]);
        }
    }
    $("#message").html('');
}

function clearCompounds() {
    // Remove any existing compounds before re-adding
    $('.compound').remove();
}

function openFile() {
    // Show the reprocess button
    $("#reprocess").show();

    var input = document.getElementById("experiment_file");
    var reader = new FileReader();
    reader.onload = function(){
        parseCSV($.csv.toArrays(reader.result));
    };
    reader.readAsText(input.files[0]);
}

function escape_regexp(text) {
  return text.replace(/[-[\]{}()*+?.,\\^$|#\s]/g, "\\$&");
}

$.expr[':'].textEquals = function (a, i, m) {
  return $(a).text().match("^" + escape_regexp(m[3]) + "$");
};


$( "#compound_search" ).autocomplete({
    minLength: 2,
    delay: 0,
    source: function(request, response_callback) {
        // Filter the results based on what GISSMO has available
        $.getJSON("http://webapi.bmrb.wisc.edu/v2/instant", { database: "metabolomics", term : request.term },
            function (response_original) {
                response = [];
                for (i=0; i<response_original.length; i++){
                    if (valid_entries.indexOf(response_original[i].value) >= 0){
                        response.push(response_original[i]);
                    }
                }
                response_callback(response);
            }
        );


    },
    select: function(event, ui) {
        addCompound(ui.item);
        return false;
    }
});/*.data("ui-autocomplete")._renderItem = function (ul, item) {
     return add_color_span_instant(ul, item, "compound_search");
};*/

// Use this to highlight the query words in a given text
function highlight_words(words, text){
    var regex = new RegExp("(" + words.join("|") + ")", "ig");
    return text.replace(regex, '<strong>$1</strong>');
}

function add_color_span_instant(ul, item, id) {

    var terms = document.getElementById(id).value.split(/[ ,]+/);
    var display = highlight_words(terms, item.value + ": " + item.label);

    var hidden_div = $('<div style="display: none" class="instant_search_extras"></div>');

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
