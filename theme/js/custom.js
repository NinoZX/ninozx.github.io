// show price list mobile
$(document).ready(function () {

    function checkWindowSize() {
        if ($(window).width() < 768) {
            $(".price-list-desktop").addClass("hidden");
            $(".price-list-mobile").removeClass("hidden");
        } else {
            $(".price-list-desktop").removeClass("hidden");
        }
    }

    checkWindowSize();

    $(window).on("resize", function () {
        checkWindowSize();
    });
});