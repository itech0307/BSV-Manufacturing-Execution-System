let scanner = new Instascan.Scanner({ video: document.getElementById('qr-preview') });
scanner.addListener('scan', function (content) {
    const url = new URL(window.location.href);
    const userName = url.searchParams.get("userName");
    const modifiedUserName = userName ? userName.slice(0, -2) : "";

    // AJAX를 사용하여 Django 뷰에 QR 코드 내용 전달
    $.ajax({
        url: window.location.pathname,  // Django 뷰의 URL
        type: 'GET',
        data: { 'qrContent': content },
        success: function(response) {
            if (response.status === "success") {
                $('#qrResult').text(response.order_number);
        
                // order_information 값을 테이블 형태로 표시
                let orderInfoHtml = '';
                const keys = ['item', 'pattern', 'color_code', 'customer', 'order_qty', 'order_type', 'brand', 'qty_unit'];
                keys.forEach(key => {
                    orderInfoHtml += `<tr><th>${key}</th><td>${response.order_information[key] || '-'}</td></tr>`;
                });
                $('#orderInfo').html(orderInfoHtml);                
                $('#kiosk').modal('show');
            } else {
                $('#qrResult').text(response.message);
                $('#kiosk').modal('show');
            }
        }
    });
});

Instascan.Camera.getCameras().then(function (cameras) {
    if (cameras.length > 0) {
        scanner.start(cameras[0]);
    } else {
        showError("Please allow camera access or check if the device is functioning properly.");
    }
}).catch(function (e) {
    showError("Please allow camera access or check if the device is functioning properly.");
});

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.innerHTML = `<div class="alert alert-danger" role="alert">${message}</div>`;
    document.querySelector('.container').appendChild(errorDiv);
}