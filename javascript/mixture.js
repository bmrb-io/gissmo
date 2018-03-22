$( "form" ).submit(function( event ) {
    //console.log($( this ).serializeObject());

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
    $.getJSON("http://webapi.bmrb.wisc.edu/v2/instant",
      { database: "metabolomics", term : compound_name },
      function(compound_list) {
        console.log(compound_name, compound_list);

        // Insert error on no match
        if (compound_list.length == 0){
            var row = $("<tr><td colspan='4'>No match</td></tr>").addClass('compound').insertBefore("#compound_anchor");;
            return;
        }

        var row = $("<tr></tr>").addClass('compound');
        var control = $("<td></td>").append($('<input type="button" value="Delete">').bind('click', { row: row }, function(event) { event.data.row.remove();}));
        var sel_td = $("<td></td>").addClass("left_align");
        var sel = $("<select name='mixture[][id]'>");
        var compound = $('<input type="hidden" name="mixture[][compound]">').val(compound_list[0].label);
        $(compound_list).each(function() {
          sel.append($("<option>").attr('value', this.value).text(this.label + ' (' + this.value + ')').data('compound',this.label));
        });
        sel.change(function () {
            compound.val($("option:selected", this).data('compound'));
        });
        sel_td.append(sel, compound);


        var conc = $("<td></td>").append($('<input type="text" name="mixture[][concentration]">').val(concentration));
        var reference = $("<td></td>").append($('<input type="checkbox" name="mixture[][reference]">'));
        row.append(control, sel_td, conc, reference).insertBefore("#compound_anchor");
      })
}

function addCompound(compound, compound_id) {
    if (!compound){
        alert("Please select a compound from one of the suggestions that will appear as you type.");
        return null;
    }

    var row = $("<tr></tr>").addClass('compound');
    var control = $("<td></td>").append($('<input type="button" value="Delete">').bind('click', { row: row }, function(event) { event.data.row.remove();}));
    var compound = $("<td></td>").append($('<input type="text" name="mixture[][compound]" readonly="true">').val(compound + ' (' + compound_id + ')'))
                             .append($('<input type="hidden" name="mixture[][id]">').val(compound_id));
    var concentration = $("<td></td>").append($('<input type="text" name="mixture[][concentration]">'));
    var reference = $("<td></td>").append($('<input type="checkbox" name="mixture[][reference]">'));
    row.append(control, compound, concentration, reference).insertBefore("#compound_anchor");

    // Reset the values
    $("#compound_search").val('');
}

function findLowercaseArray(item, array) {
    var lc_ray = array[0].map(x=>x.toLowerCase());
    for (var i=0; i < lc_ray.length; i++){
        if (lc_ray[i].indexOf(item) >= 0){
            return i;
        }
    }
}

function parseCSV(csvArray){

    var compound_pos = findLowercaseArray('name', csvArray);
    var concentration_pos = findLowercaseArray('concentration', csvArray);

    for (var i=1; i<csvArray.length; i++){
        if (csvArray[i][concentration_pos]){
            addLoadedCompound(csvArray[i][compound_pos], csvArray[i][concentration_pos]);
        }
    }
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
    source: function(request, response) {
        $.getJSON("http://webapi.bmrb.wisc.edu/v2/instant", { database: "metabolomics", term : request.term },
        response);
    },
    change: function (event, ui) {
        if(!ui.item){
            //http://api.jqueryui.com/autocomplete/#event-change -
            // The item selected from the menu, if any. Otherwise the property is null
            //so clear the item for force selection
            $("#compound_search").val("");
        }

    }, select: function(event, ui) {
        addCompound(ui.item.label, ui.item.value);
        return false;
    }
})/*.data("ui-autocomplete")._renderItem = function (ul, item) {
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
