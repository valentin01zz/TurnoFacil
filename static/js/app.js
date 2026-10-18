// Small progressive enhancements. Every page works without JavaScript.
(function () {
  document.documentElement.classList.add("js");

  // Selection forms submit themselves when a choice changes (the no-JS fallback is a visible button).
  document.querySelectorAll("form[data-autosubmit]").forEach(function (form) {
    form.addEventListener("change", function (event) {
      if (event.target.matches("input[type=radio]")) {
        if (form.requestSubmit) {
          form.requestSubmit();
        } else {
          form.submit();
        }
      }
    });
  });

  // Live ticket: the chosen time and the progress bar follow what the customer fills in.
  var ticket = document.querySelector("[data-ticket]");
  var bookForm = document.getElementById("book-form");
  if (ticket && bookForm) {
    var base = parseInt(ticket.getAttribute("data-done") || "0", 10);
    var bar = ticket.querySelector("[data-ticket-bar]");
    var label = ticket.querySelector("[data-ticket-progress]");
    var slotValue = ticket.querySelector("[data-ticket-slot]");
    var slotEmpty = ticket.querySelector("[data-ticket-slot-empty]");
    var confirm = document.querySelector("[data-ticket-confirm]");

    var update = function () {
      var checked = bookForm.querySelector("input[name=start_at]:checked");
      var name = bookForm.querySelector("[name=customer_name]");
      var phone = bookForm.querySelector("[name=customer_phone]");
      var email = bookForm.querySelector("[name=customer_email]");
      var contact = name && phone && email &&
        name.value.trim() !== "" && phone.value.replace(/\D/g, "").length >= 6 && /.+@.+\..+/.test(email.value);
      var done = base + (checked ? 1 : 0) + (contact ? 1 : 0);
      if (bar) { bar.style.width = (done * 20) + "%"; }
      if (label) { label.textContent = done >= 5 ? "¡Todo listo! Confirmá abajo." : "Paso " + Math.min(done + 1, 5) + " de 5"; }
      if (slotValue && slotEmpty) {
        if (checked) {
          slotValue.textContent = checked.getAttribute("data-label");
          slotValue.hidden = false;
          slotEmpty.hidden = true;
        } else {
          slotValue.hidden = true;
          slotEmpty.hidden = false;
        }
      }
      if (confirm) { confirm.disabled = done < 5; }
    };
    bookForm.addEventListener("input", update);
    bookForm.addEventListener("change", update);
    update();
  }

  // Copy the public booking link. The clipboard API needs HTTPS or localhost; fall back otherwise.
  document.querySelectorAll("[data-copy]").forEach(function (button) {
    button.addEventListener("click", function () {
      var input = document.getElementById(button.getAttribute("data-copy"));
      input.select();
      var done = function (copied) {
        button.textContent = copied ? "¡Copiado!" : "Seleccionado: copialo con el teclado";
      };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(input.value).then(function () { done(true); }, function () { done(false); });
      } else {
        done(document.execCommand("copy"));
      }
    });
  });

  // Open the day strip on the chosen day, else today, else the first bookable day.
  // Only the strip scrolls sideways; the page itself does not move.
  document.querySelectorAll(".days").forEach(function (strip) {
    var target = strip.querySelector(".day.selected") ||
      strip.querySelector(".day.today:not(:disabled)") ||
      strip.querySelector(".day:not(:disabled)");
    if (target) {
      strip.scrollLeft = target.offsetLeft - strip.offsetLeft - 8;
    }
  });
})();
