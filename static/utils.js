/*
 * Sets up the element $e with handlers for having the mouse over it, having
 * the mouse leave it, and being clicked on. Also sets it up so that the css 
 * class .hovered is turned on and off for the element, depending on whether 
 * mouse is over it.
 *
 * hover_on and hover_off accept the DOM element being hovered.
 * click, on the other hand, accepts the jQuery event. Access the DOM object
 *   in the usual way using the this object. 
 */
var hoverify = function($e, hover_on, hover_off, click) {
    $e.on("mouseenter.hover",
         function (e) {
             if (! $(this).hasClass('hovered')) {
                 $(this).addClass('hovered');
                 hover_on(this);
             }
         })
        .on("mouseleave.hover",
            function (e) {
                if ($(this).hasClass('hovered')) {
                    $(this).removeClass('hovered');
                    hover_off(this);
                }    
            })
        .on("click.hover", click);
};    
