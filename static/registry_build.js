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

var hoverify_delete = function($e) {
    hoverify($e,
             function (elmt) {
             },
             function (elmt) {
             },
             function (elmt) {
             });
    hoverify($e.find('.x'),
             function (elmt) {
                 $(elmt).attr('src', '/static/red_x_12.png');
             },
             function (elmt) {
                 $(elmt).attr('src', '/static/gray_x_12.png');
             },
             function (elmt) {
             });

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
        $(section_id).append('<li class="item">' + data.num_wanted + " " + data.name + "</li>");
        $li = $(add_li_code(data.section));
        $li.appendTo($(section_id));
        $li.find('.add_form').addClass('hidden').submit(submit_new_item);
        hoverify_add($li, "new item");                
    };
    $.post("",
           {ajax: 1,
            request_type: 'add_item',
            num_wanted: $(this).children('.num_wanted').val(), 
            name: $(this).children('.name').val(),
            section: $(this).children('.section').val()},
           item_added,
           "json");
    e.preventDefault();
};

var submit_delete_item = function (e) {
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
    hoverify_delete($('li.item'));
                  
});