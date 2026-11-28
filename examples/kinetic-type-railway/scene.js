// === BOOTSTRAP ===
(function () {
    var v = window.__OMNIFRAME_COMPOSITION__.variables;
    // One card per beat: when it is on screen, how big, where, and what
    // decoration travels with it. The reference is a sequence of single
    // words, so the scene is a sequence too.
    var beats = [
        { t: 0.0, d: 1.0, text: "HI THERE", size: 90, deco: "underline", ul: 0.44, ulw: 0.17 },
        { t: 1.0, d: 1.0, text: "LONDON<br>NORTHWESTERN<br>RAILWAY", size: 104, deco: "brush", dotted: true },
        { t: 2.0, d: 1.0, text: "WE HAVE", size: 90, deco: "underline", ul: 0.12, ulw: 0.14 },
        { t: 3.0, d: 1.0, text: "TO<br>DO", size: 132, deco: "underline", ul: 0.06, ulw: 0.2 },
        { t: 4.0, d: 1.0, text: "TO GET", size: 96, deco: "rays" },
        { t: 5.0, d: 1.0, text: "A", size: 380, left: true, deco: "brush" },
        { t: 6.0, d: 1.0, text: "OUR", size: 62 },
        { t: 7.0, d: 1.0, text: "WILL", size: 62 },
        { t: 8.0, d: 1.0, text: "THAT", size: 78 },
        { t: 9.0, d: 1.0, text: "WE&#39;RE", size: 62 },
        { t: 10.0, d: 1.0, text: "TO MAKING", size: 84, deco: "underline", ul: 0.52, ulw: 0.2 },
        { t: 11.0, d: 1.0, text: "USANDS", size: 64, left: true },
        { t: 12.0, d: 1.0, text: "THOUSAND", size: 104, dotted: true, deco: "line" },
        { t: 13.0, d: 1.0, text: "JOURNEYS", size: 94, deco: "brush" },
        { t: 14.0, d: 1.0, text: "EFFICIENT", size: 108, deco: "splat" },
        { t: 15.0, d: 1.0, text: "FOR", size: 62 },
        { t: 16.0, d: 1.0, text: "THEY", size: 92 },
        { t: 17.0, d: 1.0, text: "THAT&#39;S THE", size: 58 },
        { t: 18.0, d: 1.0, text: "OF IT", size: 84 },
        { t: 19.0, d: 1.04, text: "", size: 60, logo: true },
    ];
    function brushSvg(kind) {
        if (kind === "rays") {
            var rays = "";
            for (var i = 0; i < 44; i += 1) {
                var angle = (i / 44) * Math.PI * 2;
                var x1 = 640 + Math.cos(angle) * 120;
                var y1 = 340 + Math.sin(angle) * 120;
                var x2 = 640 + Math.cos(angle) * 330;
                var y2 = 340 + Math.sin(angle) * 330;
                rays += "<line x1=\"" + x1.toFixed(1) + "\" y1=\"" + y1.toFixed(1)
                    + "\" x2=\"" + x2.toFixed(1) + "\" y2=\"" + y2.toFixed(1)
                    + "\" stroke=\"#FFFFFF\" stroke-width=\"3\" />";
            }
            return rays;
        }
        if (kind === "splat") {
            var dots = "";
            var marks = [[470, 250], [790, 240], [520, 440], [780, 430], [640, 190],
                [430, 330], [850, 330], [600, 470], [700, 300]];
            for (var j = 0; j < marks.length; j += 1) {
                dots += "<ellipse cx=\"" + marks[j][0] + "\" cy=\"" + marks[j][1]
                    + "\" rx=\"12\" ry=\"26\" fill=\"#F6C8D6\" transform=\"rotate("
                    + (j * 27) + " " + marks[j][0] + " " + marks[j][1] + ")\" />";
            }
            return dots;
        }
        return "<path d=\"M 330 300 Q 640 120 950 300 Q 640 430 330 300 Z\" fill=\"none\""
            + " stroke=\"#F6C8D6\" stroke-width=\"26\" stroke-linecap=\"round\" />";
    }
    window.__B__ = { v: v, beats: beats, brushSvg: brushSvg };
})();

// === FRAME ===
(function () {
    var b = window.__B__;
    var word = document.getElementById("word");
    var underline = document.getElementById("underline");
    var brush = document.getElementById("brush");
    var splat = document.getElementById("splat");
    var logo = document.getElementById("logo");
    var tagline = document.getElementById("tagline");

    function clamp(x) { return x < 0 ? 0 : (x > 1 ? 1 : x); }
    function seg(t, from, to) { return clamp((t - from) / (to - from), 0, 1); }
    function easeOut(p) { return 1 - Math.pow(1 - p, 3); }

    window.seek = function (t) {
        var active = null;
        for (var i = 0; i < b.beats.length; i += 1) {
            var beat = b.beats[i];
            if (t >= beat.t && t < beat.t + beat.d) { active = beat; break; }
        }
        word.style.opacity = "0";
        underline.style.opacity = "0";
        brush.style.opacity = "0";
        splat.style.opacity = "0";
        logo.style.opacity = "0";
        tagline.style.opacity = "0";
        if (!active) return;
        var p = easeOut(seg(t, active.t, active.t + 0.42));
        if (active.logo) {
            logo.style.opacity = String(p);
            tagline.style.opacity = String(seg(t, active.t + 0.45, active.t + 0.8));
            return;
        }
        word.className = (active.left ? "left " : "") + (active.dotted ? "dotted" : "");
        word.innerHTML = active.text;
        word.style.fontSize = active.size + "px";
        word.style.opacity = String(p);
        word.style.transform = "translateY(-50%) scale(" + (0.82 + 0.18 * p) + ") translateY("
            + ((1 - p) * 26) + "px)";
        if (active.deco === "underline") {
            underline.style.left = Math.round(1280 * active.ul) + "px";
            underline.style.top = Math.round(360 + active.size * 0.62) + "px";
            underline.style.width = Math.round(1280 * active.ulw) + "px";
            underline.style.opacity = String(seg(t, active.t + 0.55, active.t + 0.8));
        } else if (active.deco === "line") {
            underline.style.left = "150px";
            underline.style.top = "470px";
            underline.style.width = "980px";
            underline.style.opacity = String(seg(t, active.t + 0.6, active.t + 0.85));
        } else if (active.deco === "brush" || active.deco === "rays") {
            brush.innerHTML = b.brushSvg(active.deco);
            brush.style.opacity = String(seg(t, active.t + 0.2, active.t + 0.6));
        } else if (active.deco === "splat") {
            splat.innerHTML = b.brushSvg("splat");
            splat.style.opacity = String(seg(t, active.t + 0.25, active.t + 0.65));
        }
    };

    window.seek(window.__OMNIFRAME_FRAME__ / window.__OMNIFRAME_FPS__);
})();