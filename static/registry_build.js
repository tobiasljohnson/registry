/*
 * Sets up the javascript for adding new items to the registry.
 */
var hoverify_add = function($e, hover_text) {
    hoverify($e,
             function (elmt) { // hover_on
                 $(elmt).prepend('<span class="add_hover">' + hover_text + '</span>');
             },
             function (elmt) { // hover_off
                 $(elmt).children(":first-child").remove();
             },
             function (event) { // click
                 if ($(this).hasClass('hovered')) {
                     $(this).removeClass('hovered')
                         .children(':first-child').remove();
                 }
                 $(this).off('mouseenter.hover')
                     .off('mouseleave.hover')
                     .off('click.hover')
                     .addClass('expanded')
                     .children('.add_form').removeClass('hidden').children('.first_focus').focus();
             });
}


var li_code = function(id, num_wanted, name) {
    return '<li class="item" id="' + id + '">' + num_wanted + ' ' + name + '<form class="delete_form" action="" method="post"><input type="hidden" name="request_type" value="delete_item"><input type="hidden" name="item_key" class="item_key" value="' + id + '"><input type="submit" class="x" value=""><img class="spinning" src="/static/loading_12.gif" style="display: none"></form></li>';
}

var add_li_code = function (section) {
    return '<li class="add_new_item"><form action="" method="post" autocomplete="off" class="add_form"><input type="hidden" name="request_type" value="add_item"><input type="hidden" name="section" class="section" value="' + section + '"><input type="text" size="3" name="num_wanted" class="num_wanted first_focus" placeholder="#"><input type="text" name="name" class="name" placeholder="things wanted"><input type="submit" value="Add"></form></li>';
};


var submit_new_item = function (e) {
    var that = this;
    var item_added = function (data, textStatus, jqXHR) {
        $(that).parent().remove();
        console.log(data.section);
        var section_id;
        if (data.section === "") {
            section_id = "#nosection";
        } else {
            section_id = "#section_" + data.section
        }
        $li = $(li_code(data.id, data.num_wanted, data.name));
        $li.appendTo($(section_id));
        $li.children('.delete_form').submit(submit_delete_item);
        

        $li = $(add_li_code(data.section));
        $li.appendTo($(section_id));
        $li.children('.add_form').addClass('hidden').submit(submit_new_item);
        hoverify_add($li, "new item");                
    };
    frm = $(this);
    $.post("",
           {ajax: 1,
            request_type: 'add_item',
            num_wanted: frm.children('.num_wanted').val(), 
            name: frm.children('.name').val(),
            section: frm.children('.section').val()},
           item_added,
           "json");
    
    e.preventDefault();
};

var submit_delete_item = function (e) {
    var that = this;
    
    /*
     * Callback for when server responds to ajax request.
     */
    var item_deleted = function (data, textStatus, jqXHR) {
        if (data.item_key != 0) {
            $('#' + data.item_key).remove();
        }
    };
    $.post("",
           {ajax: 1,
            request_type: 'delete_item',
            item_key: $(this).children('.item_key').val()},
           item_deleted,
           "json");
    $(this).children('.x').hide();
    $(this).children('.spinning').show();
    e.preventDefault();    
}

var submit_new_section = function (e) {
    e.preventDefault();
    var name = $(this).children('.name').val();
    if (name.length > 0) {
        var sections = $('div.registry_section');
        var i = 0;
        var sec_name = "";
        while (i < sections.length) {
            var header = $(sections[i]).children('h2');
            if (header.length > 0) {
                sec_name = header.html();
            } else {
                sec_name = "";
            }
            console.log(i);
            console.log(sec_name);
            if (sec_name.toLowerCase() >= name.toLowerCase()) {
                break;
            }
            ++i; 
        }
        var $new_div = $('<div class="registry_section"><h2>' +
                         name + '</h2><ul id="section_' + name +
                         '">' + add_li_code(name) + '</ul></div>');
        if (i < sections.length) {
            if (sec_name === name) { //issue some kind of warning about how name
            } else { //already exists
                $(sections[i]).before($new_div);
                $new_div.find('.add_form').submit(submit_new_item)
                    .children('.first_focus').focus();
            }
        } else {
            $(sections.get(-1)).after($new_div);
            $new_div.find('.add_form').submit(submit_new_item)
                    .children('.first_focus').focus();            
        }
        $(this).addClass('hidden').children('.name').val("");
        hoverify_add($(this).parent(), "new section");
    } else { // tried to submit blank name--issue warning
    }
};

$(function () {
    /*
     * Set things up for javascript enabled browser:
     */
    $('.add_new_item > .add_form').addClass('hidden')
        .submit(submit_new_item);
    $('.add_new_section > .add_form').addClass('hidden')
        .submit(submit_new_section);
    $('.delete_form').submit(submit_delete_item);
    $('.x').removeClass('nojs');

    hoverify_add($('.add_new_item'), "new item");
    hoverify_add($('.add_new_section'), "new section");
                  
});