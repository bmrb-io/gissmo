var plot;
var spectralStore = {};
var userSpectra = null;

$( "form" ).submit(function( event ) {
    event.preventDefault();
    reGraph();
});

function reGraph(){

    var mixture = $( "#upload" ).serializeObject()['mixture'];
    var layout = {
        xaxis: {
            title: 'PPM',
            autorange: 'reversed',
            titlefont: {
                family: 'Arial, sans-serif',
                size: 18,
                color: 'black'
            }
        },
        yaxis: {
            fixedrange: false
        },
        showlegend: true
    };

    var data = [];
    var concentrations = [];
    var ref_id = 0;
    var max_concentration = 0;

    // If there is a user spectra, add it
    var userSpectraScale = 1;
    if (userSpectra){

        var maxPeak = 0;
        var maxPeakPos = 0;
        for (var i=0; i < userSpectra['x'].length; i++){
            if (userSpectra['y'][i] > maxPeak){
                maxPeak = userSpectra['y'][i];
                maxPeakPos = userSpectra['x'][i];
            }
        }

        userSpectraScale = maxPeak * $("#slider").val();
        $("#scale_factor").html($("#slider").val() + " scale factor.");
    }

    // Mixture calculations and scaling
    if (typeof mixture !== 'undefined') {
        for (var i = 0; i < mixture.length; i++) {
            var concentration = parseFloat(mixture[i]['concentration']);
            if (concentration === undefined) {
                concentration = 0;
            }
            concentrations.push(concentration);
            if (concentration > max_concentration) {
                max_concentration = concentration;
                ref_id = i;
            }
        }

        if (max_concentration == 0) {
            alert('Must specify the concentration of at least one compound.');
            return;
        }

        for (var i = 0; i < concentrations.length; i++) {
            var concentration_coefficient = concentrations[i] / concentrations[ref_id];
            var comp = mixture[i];
            data.push(getTrace(retrieveData(comp['id']), comp['compound'], concentration_coefficient * userSpectraScale));
        }

        // Calculate the mixture
        data.push(getMixtureTrace(data, 64000));
    }

    if (userSpectra) {
        // Insert the user spectra first
        data.splice(0, 0, userSpectra);
    }

    // Keep the zoom if the user has zoomed
    if (plot){
        layout.xaxis.range = plot.layout.xaxis.range;
        delete layout.xaxis.autorange;
        layout.yaxis.range = plot.layout.yaxis.range
        delete layout.yaxis.autorange;
    }

    Plotly.newPlot('myDiv', data, layout, {scrollZoom: true}).then(function(result) {
        plot = result;
    });

};

$("#fieldstrength").change(function () {
    var mixture = $( "#upload" ).serializeObject()['mixture'];
    for (var i=0; i < mixture.length; i++){
        bindData(mixture[i]['id']);
    }
});

function bindData(id){
    var freq = $("#fieldstrength").val();
    if (!(freq in spectralStore)){
        spectralStore[freq] = {};
    }
    return getJSON("/entry/" + id + "/simulation_1/sim_" + $("#fieldstrength").val() + "MHz.json", function(err, data) {
        spectralStore[freq][id] = data;
    });
}

function retrieveData(id){
    var freq = $("#fieldstrength").val();
    if ((!(freq in spectralStore)) || (!(id in spectralStore[freq]))){
        bindData(id);
        alert("Still fetching the data for the newly selected frequency. Not all compounds loaded. Please try again in a few moments.");
        return [[],[]];
    }
    return spectralStore[freq][id];
}

class spectralResolver {
  constructor(trace) {
    this.x = trace['x'];
    this.y = trace['y'];
    this.xPos = 0;
    this.name = trace['name'];
  }

  getY(x){
    while (x > this.x[this.xPos]){
        this.xPos += 1;
    }

    // Exact match
    if (x === this.x[this.xPos]){
        return this.y[this.xPos];
    } else {
        // If it is the last point (or past it), return it
        if (this.xPos === this.x.length -1){
            return this.y[this.xPos];
        }

        var slope = (this.y[this.xPos+1] - this.y[this.xPos]) / (this.x[this.xPos+1]/this.x[this.xPos]);

        // Add the slope between the next two points to this x value to estimate between the points
        return this.y[this.xPos] + slope*(x-this.x[this.xPos]);
    }

  }
}

// Generate the mixture trace
function getMixtureTrace(traces, resolution) {
    var resolvers = [];
    var interval = 13/resolution;

    for (var i = 0; i < traces.length; i++) {
        resolvers.push(new spectralResolver(traces[i]));
    }

    // Empty array
    var sum = Array.apply(null, Array(resolution)).map(Number.prototype.valueOf,0);
    var xList = [];

    for (var i=0; i<resolution; i++){
        var xPos = -1 + i*interval;
        xList[i] = xPos;
        for (var n=0; n<resolvers.length; n++){
            sum[i] += resolvers[n].getY(xPos);
        }
    }

    return  {
        x: xList,
        y: sum,
        name: 'Mixture',
        marker: {
            color: 'rgb(255, 0, 0)',
            size: 12
        },
        type: 'lines'
    };

}

// add a spectra to the plot. First scale the spectra by the coefficient.
function getTrace(data, name, coefficient) {

    var localData = [[],[]];

    // Scale based on the coefficient
    for (var i=0; i<data[1].length; i++){
        localData[1][i] = data[1][i] * coefficient;
        localData[0][i] = data[0][i];
    }

    return  {
        x: localData[0],
        y: localData[1],
        name: name,
        marker: {
            color: 'rgb(0, 255, 0)',
            size: 12
        },
        type: 'lines'
    };
}


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
            var id = 0;
            $(compound_list).each(function() {
                if (valid_entries.indexOf(this.value) >= 0){
                    if (first){
                        compound_id.val(this.value);
                        inchi.val(this.inchi);
                        first = false;
                        id = this.value;
                    }
                    var option = $("<option>").attr('value', this.label).text(this.label + ' (' + this.value + ')').data('compound_id',this.value).data('inchi_string',this.inchi);
                    one_valid = true;
                    sel.append(option);
                }
            });
            sel.change(function () {
                var id = $("option:selected", this).data('compound_id');
                compound_id.val(id);
                inchi.val($("option:selected", this).data('inchi_string'));
                bindData(id);
            });
            sel_td.append(sel);
            sel_td.append(inchi);

            // Insert error on no match
            if ((compound_list.length === 0) || (!one_valid)){
                var control_nomatch = $("<tr></tr>").addClass('compound').insertBefore("#compound_anchor");
                control_nomatch.append($('<td><input type="button" value="Delete"></td>').bind('click', { row: control_nomatch }, function(event) { event.data.row.remove();}));
                control_nomatch.append($("<td>" + compound_name + "</td>").addClass('left_align'));
                control_nomatch.append($("<td></td>").html('No match'));
                control_nomatch.append($("<td></td>").html(concentration));
                control_nomatch.append($("<td></td>"));
                return;
            }

            var conc = $("<td></td>").append($('<input type="text" name="mixture[][concentration]">').val(concentration));
            row.append(control, sel_td, compound_id_td, conc).insertBefore("#compound_anchor");

            bindData(id);
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
    row.append(control, compound_td, comp_id, concentration).insertBefore("#compound_anchor");

    // Reset the values
    $("#compound_search").val('');
    bindData(selection.value);
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

function processCompoundCSV(csvArray){

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
        processCompoundCSV($.csv.toArrays(reader.result));
    };
    reader.readAsText(input.files[0]);
}


function loadSpectraCSV(csvArray){

    var ppm_pos = findLowercaseArray('ppm', csvArray);
    var amplitude_pos = findLowercaseArray('val', csvArray);
    if (amplitude_pos < 0){
        amplitude_pos = findLowercaseArray('amplitude', csvArray);
    }

    var start = 1;
    if ((ppm_pos < 0 ) && (amplitude_pos < 0)){ start = 0}
    if (ppm_pos < 0){ ppm_pos = 0; }
    if (amplitude_pos < 0){ amplitude_pos = 1; }

    var tmpSpectra = [[],[]];
    for (var i=start; i<csvArray.length; i++){
        if (csvArray[i][amplitude_pos]){
            var ppm = parseFloat(csvArray[i][ppm_pos]);
            var val = parseFloat(csvArray[i][amplitude_pos]);
            if (ppm && val){
                tmpSpectra[0].push(ppm);
                tmpSpectra[1].push(val);
            }
        }
    }

    if (tmpSpectra[0].length > 0){
        userSpectra =   {
            x: tmpSpectra[0],
            y: tmpSpectra[1],
            name: 'Uploaded Spectra',
            marker: {
                color: 'rgb(0, 0, 255)',
                size: 12
            },
            type: 'lines'
        };
    }
}


function openSpectraFile() {
    $("#slidercontainer").show();

    // Show the reprocess button
    var reader = new FileReader();
    reader.onload = function(){
        userSpectra = null;
        loadSpectraCSV($.csv.toArrays(reader.result));
        if (!userSpectra){
            loadSpectraCSV($.csv.toArrays(reader.result, {"separator" : "\t"}));
        }
        reGraph();
    };
    reader.readAsText(document.getElementById("spectra_file").files[0]);
}

$( "#compound_search" ).autocomplete({
    minLength: 2,
    delay: 0,
    source: function(request, response_callback) {
        // Filter the results based on what GISSMO has available
        $.getJSON("http://webapi.bmrb.wisc.edu/v2/instant", { database: "metabolomics", term : request.term },
            function (response_original) {
                var response = [];
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
});

// Use this to highlight the query words in a given text
function highlight_words(words, text){
    var regex = new RegExp("(" + words.join("|") + ")", "ig");
    return text.replace(regex, '<strong>$1</strong>');
}

// Used to fetch spectra off the server
var getJSON = function(url, callback) {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.responseType = 'json';
    xhr.onload = function() {
      var status = xhr.status;
      if (status === 200) {
        callback(null, xhr.response);
      } else {
        callback(status, xhr.response);
      }
    };
    xhr.send();
};



function downloadCSV(){
    let csvContent = "ppm,val\r\n";
    var mixture = [plot.data[plot.data.length-1]['x'], plot.data[plot.data.length-1]['y']];
    for (var i=0; i<mixture[0].length; i++) {
        let row = mixture[0][i].toFixed(6) + "," + mixture[1][i].toFixed(6);
        csvContent += row + "\r\n";
    }

    var a = document.createElement("a");
    document.body.appendChild(a);
    a.style = "display: none";
    var blob = new Blob([csvContent], {type: "octet/stream"}),
        url = window.URL.createObjectURL(blob);
    a.href = url;
    a.download = 'mixture.csv';
    a.click();
    window.URL.revokeObjectURL(url);

}






