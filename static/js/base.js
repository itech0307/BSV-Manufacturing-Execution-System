function generateQRCode() {
  const table = document.querySelector(".table-report");
  const rows = table.querySelectorAll("tbody tr");
  const orderNumbers = Array.from(rows).map((row) =>
    row.cells[0].textContent.trim()
  );

  const csrftoken = getCookie("csrftoken");
  const payload = {
    action: "download_to_qrcard",
    order_numbers: orderNumbers.join(","),
  };

  fetch("/data_monitoring/order_search/", {
    method: "POST",
    headers: {
      "X-CSRFToken": csrftoken,
      "Content-Type": "application/json; charset=utf-8",
    },
    body: JSON.stringify(payload),
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error("Network response was not ok");
      }
      return response.blob();
    })
    .then((blob) => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "qrcard.xlsx";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    })
    .catch((error) => {
      console.error("Error:", error);
      alert("Failed to download file.");
    });
}

function handleColumnToggle() {
  const checkboxes = document.querySelectorAll(".column-toggle");
  const currentPage = window.location.pathname;

  checkboxes.forEach((checkbox) => {
    const columnName = checkbox.dataset.column;
    const storageKey = `${currentPage}_${columnName}_visible`;

    // Restore saved state or set default value
    const savedState = localStorage.getItem(storageKey);
    const isChecked = savedState === null ? true : savedState === "true";
    checkbox.checked = isChecked;
    toggleColumnVisibility(columnName, isChecked);

    // When checkbox state changes, save and handle column visibility
    checkbox.addEventListener("change", function () {
      localStorage.setItem(storageKey, this.checked);
      toggleColumnVisibility(columnName, this.checked);
    });
  });
}

// Function to handle column visibility
function toggleColumnVisibility(columnName, isVisible) {
  const columnClass = columnName.toLowerCase() + "-col";
  const cells = document.querySelectorAll(`.${columnClass}`);
  cells.forEach((cell) => {
    cell.style.display = isVisible ? "" : "none";
  });
}

// Execute when page loads
document.addEventListener("DOMContentLoaded", handleColumnToggle);

document
  .getElementById("searchPopup")
  .addEventListener("keypress", function (event) {
    if (event.keyCode === 13) {
      // Enter key's keyCode is 13
      event.preventDefault(); // Prevent form from being submitted automatically
      toggleSearchPopup(); // Call the search execution function
    }
  });

document.addEventListener("click", function (event) {
  var popup = document.getElementById("searchPopup");
  var searchButton = document.querySelector(
    'button[onclick="toggleSearchPopup()"]'
  );
  // If the popup is open and the clicked element is not inside the popup and not the search button, close the popup
  if (
    popupVisible &&
    !popup.contains(event.target) &&
    !searchButton.contains(event.target)
  ) {
    closeSearchPopup(popup);
    popupVisible = false;
  }
});

function exportTableToExcel() {
  var wb = XLSX.utils.table_to_book(document.querySelector("table"), {
    sheet: "Sheet JS",
    raw: true, // Process all data as raw strings
  });
  var wbout = XLSX.write(wb, {
    bookType: "xlsx",
    bookSST: true,
    type: "binary",
  });

  function s2ab(s) {
    var buf = new ArrayBuffer(s.length);
    var view = new Uint8Array(buf);
    for (var i = 0; i < s.length; i++) view[i] = s.charCodeAt(i) & 0xff;
    return buf;
  }

  // Get the header content
  var headerContent = document.querySelector("h2").textContent.trim();

  // Set the file name to the header content
  saveAs(
    new Blob([s2ab(wbout)], { type: "application/octet-stream" }),
    headerContent + ".xlsx"
  );
}

function showSearchPopup() {
  var popup = document.getElementById("searchPopup");
  var searchButton = document.querySelector(
    'button[onclick="showSearchPopup()"]'
  );

  var buttonRect = searchButton.getBoundingClientRect(); // Get the position information of the search button
  var popupHeight = popup.clientHeight;

  popup.style.top = buttonRect.bottom + "px"; // Set the popup to be below the button
  popup.style.left = buttonRect.right + "px";

  popup.style.display = "block";
  setTimeout(function () {
    popup.style.opacity = "1";
  }, 300);
}

function closeSearchPopup() {
  var popup = document.getElementById("searchPopup");
  popup.style.opacity = "0";
  setTimeout(function () {
    popup.style.display = "none";
  }, 300);
}

var popupVisible = false; // Add a variable to indicate the state of the pop-up window

function openListSearchModal() {
  $("#listSearchModal").modal("show");
}

function closeListSearchModal() {
  $("#listSearchModal").modal("hide");
}

function searchListOrders() {
  const input = document.getElementById("listOrderInput").value.trim();

  if (input === "") {
    alert("Please enter at least one order number.");
    return;
  }

  const orderLines = input.split("\n");
  const orderNumbers = orderLines.map((line) =>
    line.replace(/\t/g, "-").trim()
  );
  document.getElementById("listOrderInput").value = orderNumbers;
  const form = document.getElementById("listOrderForm"); // Correctly referencing the form object
  form.submit();
  $("#listSearchModal").modal("hide");
}

function validateOrderNumber() {
  const orderNumber = document.getElementById("order_number").value;
  if (orderNumber.length < 6) {
    alert("Order number must be at least 6 characters long.");
    return false;
  }
  return true;
}

function validateDates(startDateInput, endDateInput) {
  if (startDateInput && endDateInput) {
    var startDate = new Date(startDateInput);
    var endDate = new Date(endDateInput);
    var sixtyDays = 60 * 24 * 60 * 60 * 1000; // Convert 60 days to milliseconds

    var timeDiff = endDate - startDate;

    if (timeDiff > sixtyDays) {
      alert("Date range cannot exceed 60 days.");
      return false;
    }
  }
  return true;
}

function toggleSearchPopup() {
  var popup = document.getElementById("searchPopup");
  if (popupVisible) {
    // When the popup is open, submit the form and close the popup
    var orderNoInput = document.getElementById("orderNoInput").value;
    var itemInput = document.getElementById("itemInput").value;
    var colorCodeInput = document.getElementById("colorCodeInput").value;
    var patternInput = document.getElementById("patternInput").value;
    var customerInput = document.getElementById("customerInput").value;
    var orderTypeInput = document.getElementById("orderTypeInput").value;
    var startDateInput = document.getElementById("startDateInput").value;
    var endDateInput = document.getElementById("endDateInput").value;

    // Kiểm tra xem có ít nhất một tiêu chí tìm kiếm nào được nhập không
    // Bao gồm cả trường hợp chỉ nhập ngày tháng
    if (
      orderNoInput.trim() === "" &&
      itemInput.trim() === "" &&
      colorCodeInput.trim() === "" &&
      patternInput.trim() === "" &&
      customerInput.trim() === "" &&
      orderTypeInput.trim() === "" &&
      !startDateInput &&
      !endDateInput
    ) {
      alert("Please enter at least one search criteria.");
      return;
    }

    // Validate individual fields if they have values
    if (orderNoInput.length >= 1 && orderNoInput.length < 6) {
      alert("'OrderNo' must be at least 6 characters long.");
      return;
    }
    if (itemInput.length >= 1 && itemInput.length < 4) {
      alert("'Item' must be at least 4 characters long.");
      return;
    }
    if (colorCodeInput.length >= 1 && colorCodeInput.length < 3) {
      alert("'ColorCode' must be at least 3 characters long.");
      return;
    }
    if (patternInput.length == 1) {
      alert("'Pattern' must be at least 2 characters long.");
      return;
    }
    if (customerInput.length == 1) {
      alert("'Customer' must be at least 2 characters long.");
      return;
    }

    // Validate date range if either date is entered
    if (
      (startDateInput && !endDateInput) ||
      (!startDateInput && endDateInput)
    ) {
      alert("Please enter both Start Date and End Date.");
      return;
    }

    if (
      startDateInput &&
      endDateInput &&
      !validateDates(startDateInput, endDateInput)
    ) {
      return;
    }

    document.forms[0].submit();
    popup.style.opacity = "0";
    setTimeout(function () {
      popup.style.display = "none";
    }, 300);
  } else {
    // When the popup is closed, open it
    var searchButton = document.querySelector(
      'button[onclick="toggleSearchPopup()"]'
    );
    var buttonRect = searchButton.getBoundingClientRect();
    var leftPosition = buttonRect.right + 20;
    var windowWidth = window.innerWidth;

    if (leftPosition + 600 > windowWidth) {
      leftPosition = windowWidth - 620;
    }
    popup.style.top = buttonRect.bottom + "px";
    popup.style.left = leftPosition + "px";
    popup.style.display = "block";
    setTimeout(function () {
      popup.style.opacity = "1";
    }, 300);
  }
  popupVisible = !popupVisible;
}

// Context menu script
document.addEventListener("DOMContentLoaded", function () {
  const table = document.querySelector(".table-report");
  const contextMenu = document.getElementById("context-menu");

  table.addEventListener(
    "contextmenu",
    function (e) {
      e.preventDefault();
      clickedRow = e.target.closest("tr"); // Save the clicked row to the global variable
      const { clientX: mouseX, clientY: mouseY } = e;
      contextMenu.style.top = `${mouseY}px`;
      contextMenu.style.left = `${mouseX}px`;
      contextMenu.style.display = "block";
    },
    false
  );

  document.addEventListener(
    "click",
    function (e) {
      contextMenu.style.display = "none";
    },
    false
  );
});

function elapsedTime(timeDifferenceMs) {
  // Convert milliseconds to days, hours, and minutes
  const days = Math.floor(timeDifferenceMs / (1000 * 60 * 60 * 24));
  const hours = Math.floor(
    (timeDifferenceMs % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60)
  );
  const minutes = Math.floor(
    (timeDifferenceMs % (1000 * 60 * 60)) / (1000 * 60)
  );

  if (days > 0) {
    return `${days} days ${hours} hours`;
  } else if (hours > 0) {
    return `${hours} hours ${minutes} minutes`;
  } else {
    return `${minutes} minutes`;
  }
}

function action1() {
  if (!clickedRow) return; // If there is no clicked row, stop the function

  // Get the data attribute from the clicked row
  const dataStatus = clickedRow.getAttribute("data-status");

  // Convert the JSON string to an object (parsing)
  const statusInfo = JSON.parse(dataStatus);

  // Select the modal window elements
  const modal = document.getElementById("infoModal");
  const modalOrderDetails = document.getElementById("modalOrderDetails");

  let ProcessInfo = ``;

  for (let i = 0; i < Object.keys(statusInfo.process).length; i++) {
    let headers = "";
    let values = "";

    if (statusInfo.process[i].process == "DryPlan") {
      headers = `
              <tr style="background-color: #FF4500;">                        
                  <th>Plan Date</th>
                  <th>Process</th>
                  <th>Plan Qty</th>
                  <th>Skin Resin</th>
                  <th>Binder Resin</th>
                  <th>Base</th>
              </tr>
          `;
      values = `
              <tr>
                  <td>${statusInfo.process[i].plan_date}</td>
                  <td>${statusInfo.process[i].process} ${statusInfo.process[
        i
      ].machine.slice(-1)}</td>
                  <td>${statusInfo.process[i].plan_qty} M</td>
                  <td>${statusInfo.process[i].skin_resin}</td>
                  <td>${statusInfo.process[i].binder_resin}</td>
                  <td>${statusInfo.process[i].base}</td>
              </tr>
          `;
    } else if (statusInfo.process[i].process == "DryMix") {
      mixing_time = new Date(
        statusInfo.process[i].create_date.replace(" ", "T")
      );
      headers = `
              <tr style="background-color: #FFC107;">                        
                  <th>Date</th>
                  <th>Process</th>
          `;
      for (const key of Object.keys(statusInfo.process[i].chemical)) {
        headers += `
                  <th>${key}</th>
              `;
      }
      headers += `
              </tr>
          `;
      values = `
              <tr>
                  <td>${statusInfo.process[i].create_date.slice(0, 16)}</td>
                  <td>${statusInfo.process[i].process} ${statusInfo.process[
        i
      ].machine.slice(-1)}</td>
          `;
      values += `
                  {% if "production_managers" in user_groups %}
              `;
      for (const value of Object.values(statusInfo.process[i].chemical)) {
        values += `
                  <td>${value}</td>
              `;
      }
      values += `
                  {% else %}
              `;
      for (const value of Object.values(statusInfo.process[i].chemical)) {
        values += `
                  <td>???</td>
              `;
      }
      values += `
              </tr>
              {% endif %}
          `;
    } else if (statusInfo.process[i].process == "DryLine") {
      dryline_time = new Date(
        statusInfo.process[i].create_date.replace(" ", "T")
      );
      let swt;
      if (typeof mixing_time !== "undefined") {
        swt = elapsedTime(dryline_time - mixing_time);
      } else {
        swt = `N/A`;
      }
      headers = `
              <tr style="background-color: #5986c9;">
                  <th>Date</th>
                  <th>Process</th>
                  <th>Production Qty</th>
                  <th>Waiting</th>
              </tr>
          `;
      values = `
              <tr>                        
                  <td>${statusInfo.process[i].create_date.slice(0, 16)}</td>
                  <td>${statusInfo.process[i].process} ${statusInfo.process[
        i
      ].machine.slice(-1)}</td>
                  <td>${statusInfo.process[i].pd_qty} M</td>
                  <td>${swt}</td>
              </tr>
          `;
    } else if (statusInfo.process[i].process == "RP") {
      delami_time = new Date(
        statusInfo.process[i].create_date.replace(" ", "T")
      );
      let at;
      if (typeof dryline_time !== "undefined") {
        at = elapsedTime(delami_time - dryline_time);
      } else {
        at = `N/A`;
      }
      headers = `
              <tr style="background-color: #5986c9;">                        
                  <th>Date</th>
                  <th>Process</th>
                  <th>Delamination Qty</th>
                  <th>Aging</th>
              </tr>
          `;
      values = `
              <tr>                        
                  <td>${statusInfo.process[i].create_date.slice(0, 16)}</td>
                  <td>${statusInfo.process[i].process} ${statusInfo.process[
        i
      ].machine.slice(-1)}</td>
                  <td>${statusInfo.process[i].delami_qty} M</td>
                  <td>${at}</td>
              </tr>
          `;
    } else if (statusInfo.process[i].process == "Inspection") {
      headers = `
              <tr style="background-color: #3CB371;">                        
                  <th>Date</th>
                  <th>Process</th>
                  <th>A Grade</th>
              </tr>
          `;
      values = `
              <tr>                        
                  <td>${statusInfo.process[i].create_date.slice(0, 16)}</td>
                  <td>${statusInfo.process[i].process} ${statusInfo.process[
        i
      ].machine.slice(-1)}</td>
                  <td>${statusInfo.process[i].agrade_qty} M</td>
              </tr>
          `;
    } else if (statusInfo.process[i].process == "Printing") {
      headers = `
              <tr style="background-color: #FF8C00;">                        
                  <th>Date</th>
                  <th>Process</th>
                  <th>Quantity</th>
              </tr>
          `;
      values = `
              <tr>                        
                  <td>${statusInfo.process[i].create_date.slice(0, 16)}</td>
                  <td>${statusInfo.process[i].process} ${statusInfo.process[
        i
      ].machine.slice(-1)}</td>
                  <td>${statusInfo.process[i].print_qty} M</td>
              </tr>
          `;
    }

    if (headers && values) {
      ProcessInfo += `
        <table class="table table-bordered" style="width:100%; margin-bottom: 20px;">
            <thead>${headers}</thead>
            <tbody>${values}</tbody>
        </table>
        `;
    }
  }

  document.getElementById("modalStatusInfo").innerHTML = ProcessInfo;
  modal.style.display = "block";
}

// Function to close the modal window
const modal = document.getElementById("infoModal");
const closeModal = modal.querySelector(".close");
closeModal.onclick = function () {
  modal.style.display = "none";
};

// Function to close the modal window when clicking outside
window.onclick = function (event) {
  if (event.target == modal) {
    modal.style.display = "none";
  }
};

function action2() {
  if (!clickedRow) return;
  const my_list = clickedRow.getAttribute("data-order-number");

  const csrftoken = getCookie("csrftoken");
  const payload = {
    action: "add_to_my_list",
    my_list: my_list,
    content: { Line: true },
  };

  // console.log(JSON.stringify(payload)); // Check the data format in the log

  $.ajax({
    url: "/ppm/report/order_search/",
    type: "POST",
    headers: { "X-CSRFToken": csrftoken },
    data: JSON.stringify(payload),
    contentType: "application/json; charset=utf-8",
    dataType: "json",
    success: function (response) {
      if (response.status === "success") {
        alert("My list has been updated successfully.");
      } else if (response.status === "overlap") {
        alert("ERROR : Already exist!");
      } else {
        alert("UNKNOWN ERROR");
      }
    },
    error: function (xhr, status, error) {
      alert("Error occurred!");
    },
  });
}

// Function to get the CSRF token from the cookie
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + "=") {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

function action3() {
  alert("Now Preparing..!");
}

function action4() {
  alert("Now Preparing..!");
}

function captureTableAsImage() {
  const table = document.querySelector(".table");

  // Calculate the number of rows in the table (exclude the rows in the thead)
  const rowCount = table.querySelectorAll("tbody tr").length;

  // If the number of rows is 100 or more, do not work
  if (rowCount >= 100) {
    alert("Table is too large to capture (100 rows maximum).");
    return;
  }

  // Load html2canvas only when needed
  if (typeof html2canvas !== "function") {
    const script = document.createElement("script");
    script.src =
      "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.3.2/html2canvas.min.js";
    document.head.appendChild(script);
    script.onload = () => {
      html2canvas(table).then((canvas) => {
        canvas.toBlob(function (blob) {
          const item = new ClipboardItem({ "image/png": blob });
          navigator.clipboard.write([item]);
          alert("Table captured and copied to clipboard!");
        });
      });
    };
  } else {
    html2canvas(table).then((canvas) => {
      canvas.toBlob(function (blob) {
        const item = new ClipboardItem({ "image/png": blob });
        navigator.clipboard.write([item]);
        alert("Table captured and copied to clipboard!");
      });
    });
  }
}
