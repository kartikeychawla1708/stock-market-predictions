let highChart, lowChart, predictedHighChart, predictedLowChart;

// Show loader when data is being fetched
function showLoader() {
    document.getElementById('loader').style.display = 'flex';
}

// Hide loader when data is done loading
function hideLoader() {
    document.getElementById('loader').style.display = 'none';
}

// Handle company selection change event
function handleCompanySelection() {
    const companyList = document.getElementById('companyList');
    const selectedCompanyName = companyList.options[companyList.selectedIndex].text;
    document.getElementById("selectedCompany").textContent = selectedCompanyName;
    document.getElementById("companyNews").style.display = 'block';
    // Update the sentiment input label
    const sentimentLabel = document.querySelector('label[for="sentimentText"]');
    sentimentLabel.textContent = `Enter the media about ${selectedCompanyName}:`;
}


// Toggle sentiment input visibility based on news checkbox status
function toggleSentimentInput() {
    const newsCheckbox = document.getElementById('newsCheckbox');
    const sentimentInput = document.getElementById('sentimentInput');
    sentimentInput.style.display = newsCheckbox.checked ? "block" : "none";
}

// Make the prediction by sending data to the server
function makePrediction() {
    const companyList = document.getElementById('companyList');
    const company = companyList.value;
    const newsCheckbox = document.getElementById('newsCheckbox');
    const hasNews = newsCheckbox.checked;
    const sentimentText = hasNews ? document.getElementById('sentimentText').value.trim() : null;

    // Check if a company is selected
    if (!company) {
        alert("Please select a company before making predictions.");
        return;
    }

    // Check if sentiment input is required and non-empty
    if (hasNews && !sentimentText) {
        alert("Please enter the media update about the stock if you select the news checkbox.");
        return;
    }

    showLoader();

    fetch('/get_stock_data', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            symbol: company,
            has_news: hasNews,
            sentiment_text: sentimentText  // Send the sentiment text to the server
        })
    })
    .then(response => {
        if (!response.ok) {
            return response.text().then(text => {
                throw new Error(`HTTP error! status: ${response.status}, response: ${text}`);
            });
        }
        return response.json();
    })
    .then(data => {
        updateCharts(data);
        hideLoader();
    })
    .catch(error => {
        console.error('Error fetching data:', error);
        hideLoader();
    });
}

// Update the charts with the fetched data
function updateCharts(data) {
    const chartsArea = document.querySelector('.charts-area');
    chartsArea.style.display = 'flex';

    // Check if data has the required properties
    if (!data || !data.date || !data.high || !data.low || !data.predicted_high || !data.predicted_low || !data.predicted_dates) {
        alert("Error: Invalid data received from the server.");
        return;
    }

    // Get the last 7 actual dates, high, and low values
    const labels = data.date.slice(-7); // Last 7 actual dates
    const highData = data.high.slice(-7); // Last 7 actual high values
    const lowData = data.low.slice(-7); // Last 7 actual low values

    // Use all predicted data
    const predictedHighData = data.predicted_high; // All predicted high values
    const predictedLowData = data.predicted_low; // All predicted low values
    const predictedDates = data.predicted_dates; // All predicted dates

    updateChart('actualHighChart', 'Actual High Prices', labels, highData, 'lightgreen');
    updateChart('actualLowChart', 'Actual Low Prices', labels, lowData, 'lightcoral');
    updateChart('predictedHighChart', 'Predicted High Prices', predictedDates, predictedHighData, '#2eb82e');
    updateChart('predictedLowChart', 'Predicted Low Prices', predictedDates, predictedLowData, 'red');
}

// Function to update individual chart elements
function updateChart(chartId, label, labels, data, lineColor) {
    const chartElement = document.getElementById(chartId);
    const chartContext = chartElement.getContext('2d');

    // Check if a Chart.js instance already exists in window[chartId]
    if (window[chartId] && window[chartId] instanceof Chart) {
        window[chartId].destroy(); // Only call destroy if it's an instance of Chart
    }

    // Create a new chart instance
    window[chartId] = new Chart(chartContext, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: label,
                data: data,
                borderColor: lineColor, // Use the passed color
                borderWidth: 2,
                fill: false // No fill under the line
            }]
        },
        options: {
            scales: {
                y: {
                    beginAtZero: false,
                    title: {
                        display: true,
                        text: 'Price($)' // Updated Y-axis label
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Date'
                    }
                }
            },
            responsive: true,
            maintainAspectRatio: false
        }
    });
}

// Attach event listeners once the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function () {
    const companyList = document.getElementById('companyList');
    const newsCheckbox = document.getElementById('newsCheckbox');
    
    // Attach event listeners
    companyList.addEventListener('change', handleCompanySelection);
    newsCheckbox.addEventListener('change', toggleSentimentInput);
});
