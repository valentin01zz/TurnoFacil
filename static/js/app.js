// Small progressive enhancements. Every page works without JavaScript.
(function () {
  document.documentElement.classList.add("js");

  // On phones the panel tabs scroll sideways: bring the current one into view.
  var currentTab = document.querySelector(".panel-bar .tabs [aria-current=page]");
  if (currentTab) {
    var tabs = currentTab.parentElement;
    var offset = currentTab.getBoundingClientRect().left - tabs.getBoundingClientRect().left;
    if (tabs.scrollWidth > tabs.clientWidth) tabs.scrollLeft += offset - 16;
  }

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

  // Working hours: add rows from the formset's empty form and dim the rows marked for deletion.
  // Without JavaScript the form still has a few empty rows; the server enforces the limit.
  var addHours = document.querySelector("[data-hours-add]");
  var hoursRows = document.querySelector("[data-hours-rows]");
  var hoursTemplate = document.querySelector("[data-hours-template]");
  var totalForms = document.querySelector("[name=hours-TOTAL_FORMS]");
  if (addHours && hoursRows && hoursTemplate && totalForms) {
    var maxRows = parseInt(addHours.getAttribute("data-max"), 10);
    var limitNote = document.querySelector("[data-hours-limit]");
    var markDeleted = function (checkbox) {
      checkbox.closest("[data-hours-row]").classList.toggle("is-deleted", checkbox.checked);
    };
    var refresh = function () {
      var kept = hoursRows.querySelectorAll("[data-hours-row]:not(.is-deleted)").length;
      // The server also refuses more than twice the limit of rows sent, deleted ones included.
      var full = kept >= maxRows || parseInt(totalForms.value, 10) >= maxRows * 2;
      addHours.disabled = full;
      if (limitNote) { limitNote.hidden = !full; }
    };
    hoursRows.addEventListener("change", function (event) {
      if (event.target.matches("input[type=checkbox][name$=-DELETE]")) {
        markDeleted(event.target);
        refresh();
      }
    });
    addHours.addEventListener("click", function () {
      var index = parseInt(totalForms.value, 10);
      var html = hoursTemplate.innerHTML.replace(/__prefix__/g, index).replace("Tramo nuevo", "Tramo " + (index + 1));
      hoursRows.insertAdjacentHTML("beforeend", html);
      totalForms.value = index + 1;
      var added = hoursRows.lastElementChild.querySelector("select, input:not([type=hidden])");
      if (added) { added.focus(); }
      refresh();
    });
    hoursRows.querySelectorAll("input[type=checkbox][name$=-DELETE]:checked").forEach(markDeleted);
    addHours.hidden = false;
    refresh();
  }
})();
