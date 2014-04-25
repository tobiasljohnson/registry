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
