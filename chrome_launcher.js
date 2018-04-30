const fs = require('fs');
const chromeLauncher = require('chrome-launcher');
const CDP = require('chrome-remote-interface');
const summary = require('./util/browser-perf-summary')

//var TRACE_CATEGORIES = ["-*", "devtools.timeline", "disabled-by-default-devtools.timeline", "disabled-by-default-devtools.timeline.frame", "toplevel", "blink.console", "disabled-by-default-devtools.timeline.stack", "disabled-by-default-devtools.screenshot", "disabled-by-default-v8.cpu_profile"];
var TRACE_CATEGORIES = ["-*", "toplevel", "blink.console", "disabled-by-default-devtools.timeline", "devtools.timeline", "disabled-by-default-devtools.timeline.frame", "devtools.timeline.frame", "disabled-by-default-devtools.timeline.stack", "disabled-by-default-v8.cpu_profile", "disabled-by-default-blink.feature_usage", "blink.user_timing", "v8.execute", "netlog"];
var rawEvents = [];
var myArgs = process.argv.slice(2);

(async function () {
    let argLaunchChrome = myArgs[4].toLowerCase() === "true";
    let chrome;
    if (argLaunchChrome) {
        let chromeFlags = ['--incognito', '--ignore-certificate-errors', '--no-sandbox'];
        chrome = await chromeLauncher.launch({
            chromeFlags: chromeFlags
        });
    }
    let devtoolsPort = chrome ? chrome.port : 9222;
    console.log(`Connecting to Devtools on Port ${devtoolsPort}`);
    const client = await CDP({
        port: devtoolsPort,
        local: true // Todo: This is workaround for a Chrome bug? Check up on this later
    });
    // Get and enable domains
    const { Network, Page, Tracing, Emulation } = client;
    await Page.enable();
    // Set network settings
    await Network.enable();
    await Network.setCacheDisabled({ cacheDisabled: true });
    await Network.clearBrowserCache();
    await Network.clearBrowserCookies();
    let conditions_unlimited = {
        offline: false,
        latency: 0,
        downloadThroughput: -1,
        uploadThroughput: -1
    };
    // 2g conditions taken from EDGE(2.5G) wikipedia page
    let conditions_2g = {
        offline: false,
        latency: 300,
        downloadThroughput: 0.4 * 1000 * 1000 / 8,  // 400kbps
        uploadThroughput: 0.2 * 1000 * 1000 / 8     // 200kbps
    };
    // 3G and 4G Conditions taken from OpenSignal India
    let conditions_3g = {
        offline: false,
        latency: 160,
        downloadThroughput: 2.5 * 1000 * 1000 / 8,  // 2.5mbps
        uploadThroughput: 1.5 * 1000 * 1000 / 8     // 1.5mbps
    };
    let conditions_4g = {
        offline: false,
        latency: 70,
        downloadThroughput: 7.5 * 1000 * 1000 / 8,  // 7.5mbps
        uploadThroughput: 5.5 * 1000 * 1000 / 8     // 5.5mbps
    };
    await Network.emulateNetworkConditions(conditions_2g);

    // Todo: Remove this when using mobile sites
    // Mobile overrides for loading desktop sites
    await Network.setUserAgentOverride({
        userAgent: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.46 Safari/537.36"
    });
    await Emulation.setDeviceMetricsOverride({
        width: 980,
        height: 1524,
        deviceScaleFactor: 2,
        mobile: false
    });

    // Start Tracing
    await Tracing.start({
        "categories": TRACE_CATEGORIES.join(','),
        "options": "sampling-frequency=10000"  // 1000 is default and too slow.
    });

    // Set handlers
    Page.loadEventFired(function (data) {
        Tracing.end(function () {
            Page.captureScreenshot(function (err, res) {
                var buf = new Buffer(res.data, 'base64');
                var imageFile = myArgs[3] + '.png'
                fs.writeFileSync(imageFile, buf);
            });
        });
        //process.kill(parseInt(myArgs[4]));
        var _times = {};
        _times.load = data.timestamp;
        var times_file = myArgs[2] + '.times';
        fs.writeFileSync(times_file, JSON.stringify(_times, null, 0));
    });
    Tracing.tracingComplete(function () {
        var traceFile = myArgs[1] + '.trace';
        var summaryFile = myArgs[2];
        rawEvents = rawEvents.map(function (e) {
            return JSON.stringify(e);
            Page.captureScreenshot(function (err, res) {
                var buf = new Buffer(res.data, 'base64');
                var imageFile = myArgs[3] + '.png'
                fs.writeFileSync(imageFile, buf);
            });
        });
        fs.writeFileSync(traceFile, JSON.stringify(rawEvents, null, 0));
        console.log('Trace file: ' + traceFile);
        //console.log('You can open the trace file in DevTools Timeline panel. (Turn on experiment: Timeline tracing based JS profiler)\n')
        summary.report(summaryFile); // superfluous
        // Todo: Refactor hardcoded timeout
        let postLoadTimeout = 1000;
        setTimeout(() => {
            console.log("Killing Client/Chrome...")
            client.close();
            if (chrome)
                chrome.kill();
        }, postLoadTimeout);
    });
    //dataCOllected event send { "name": "value", "type": "array", "items": { "type": "object" } parameter as input
    Tracing.dataCollected(function (data) {
        var events = data.value;
        rawEvents = rawEvents.concat(events);
        // this is just extra but not really important
        summary.onData(events);
    });

    // Load the page
    await Page.navigate({ 'url': myArgs[0] },
        function () {
            Page.captureScreenshot(function (err, res) {
                var buf = new Buffer(res.data, 'base64');
                var imageFile = myArgs[3] + '.png'
                fs.writeFileSync(imageFile, buf);
            });
        });
})();
