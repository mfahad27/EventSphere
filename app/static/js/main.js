document.addEventListener(
    "DOMContentLoaded",
    function () {

        // Automatically hide flash messages
        setTimeout(
            function () {

                const alerts =
                    document.querySelectorAll(
                        ".alert"
                    );

                alerts.forEach(
                    function (alert) {

                        alert.style.opacity = "0";

                        setTimeout(
                            function () {
                                alert.remove();
                            },
                            400
                        );

                    }
                );

            },
            4500
        );


        // Confirm delete actions
        const deleteForms =
            document.querySelectorAll(
                "form[data-confirm-delete]"
            );

        deleteForms.forEach(
            function (form) {

                form.addEventListener(
                    "submit",
                    function (event) {

                        const confirmed =
                            confirm(
                                "Are you sure you want to delete this item?"
                            );

                        if (!confirmed) {
                            event.preventDefault();
                        }

                    }
                );

            }
        );

    }
);