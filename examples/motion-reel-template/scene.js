// === BOOTSTRAP ===
(function () {
    var v = window.__OMNIFRAME_COMPOSITION__.variables;
    var words = String(v.words).split('|');
    var ticks = document.getElementById('ticks');
    var dots = document.getElementById('dots');
    var sphere = document.getElementById('sphere');
    var glyphDots = document.getElementById('glyphDots');
    var beats = document.getElementById('beatMarks');
    var i, el;

    for (i = 0; i < 14; i++) {
        el = document.createElement('i');
        el.style.left = (i / 13 * 100) + '%';
        ticks.appendChild(el);
    }
    for (i = 0; i < 16; i++) {
        el = document.createElement('i');
        el.style.left = (i / 15 * 100) + '%';
        beats.appendChild(el);
    }
    for (i = 0; i < 36; i++) {
        el = document.createElement('i');
        el.className = 'dot';
        dots.appendChild(el);
    }
    for (i = 0; i < 160; i++) {
        el = document.createElement('i');
        sphere.appendChild(el);
    }

    // Rasterise the variable word once, then sample it into particle targets.
    // No external image or randomness: the same string always yields the same dots.
    var canvas = document.createElement('canvas');
    canvas.width = 1920;
    canvas.height = 1080;
    var ctx = canvas.getContext('2d');
    ctx.fillStyle = '#ffffff';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.font = '900 300px Arial, Helvetica, sans-serif';
    ctx.fillText(String(v.particleWord), 960, 540);
    var pixels = ctx.getImageData(0, 0, 1920, 1080).data;
    var samples = [];
    var y, x;
    for (y = 0; y < 1080; y += 9) {
        for (x = 0; x < 1920; x += 9) {
            if (pixels[(y * 1920 + x) * 4 + 3] > 100) {
                samples.push([x, y]);
            }
        }
    }
    var stride = Math.max(1, Math.ceil(samples.length / 700));
    var glyph = [];
    for (i = 0; i < samples.length; i += stride) {
        glyph.push(samples[i]);
    }
    for (i = 0; i < glyph.length; i++) {
        el = document.createElement('i');
        el.className = 'gdot';
        glyphDots.appendChild(el);
    }

    document.getElementById('ghostTop').textContent = words.join(' ');
    document.getElementById('ghostMid').textContent = words.slice().reverse().join(' ');
    document.getElementById('ghostBottom').textContent = words.join(' ');
    document.getElementById('hudTL').textContent =
        v.brand + ' / ' + v.reel.replace('&apos;', "'");

    window.__REEL_STATE__ = {
        words: words,
        beats: beats.children,
        dots: dots.children,
        sphere: sphere.children,
        glyph: glyph,
        glyphDots: glyphDots.children,
        rings: document.querySelectorAll('#ch2 .ring'),
        crosses: document.querySelectorAll('#ch2 .cross'),
        bars: document.querySelectorAll('#chart i'),
        ribbons: document.querySelectorAll('#ribbons path'),
        chapters: document.querySelectorAll('.chapter'),
        chapterNames: [
            'INTRO', 'KINETIC TYPE', 'SYSTEMS', 'PARTICLES',
            'DIMENSION', 'DATA', 'FLOW', 'OUTRO'
        ],
        targets: [parseFloat(v.m1) || 0, parseFloat(v.m2) || 0, parseFloat(v.m3) || 0],
        ringTarget: parseFloat(v.ringValue) || 0
    };
})();

// === FRAME ===
(function () {
    var s = window.__REEL_STATE__;
    var comp = window.__OMNIFRAME_COMPOSITION__;

    function clamp(x) { return x < 0 ? 0 : (x > 1 ? 1 : x); }
    function outExpo(p) { return p >= 1 ? 1 : 1 - Math.pow(2, -10 * p); }

    function activeTrack(t) {
        var list = comp.tracks;
        for (var i = 0; i < list.length; i++) {
            var tr = list[i];
            if (t >= tr.start && t < tr.start + tr.duration) {
                return { id: tr.id, u: (t - tr.start) / tr.duration };
            }
        }
        return null;
    }

    function intro(u) {
        var ball = document.getElementById('ball');
        var y = 0.22 + 0.44 * Math.min(1, u * 3)
              + 0.09 * Math.abs(Math.sin(u * Math.PI * 4)) * Math.exp(-3 * u);
        var sx = 1 + 0.12 * Math.sin(u * Math.PI * 8) * Math.exp(-4 * u);
        ball.style.top = (y * 100) + '%';
        ball.style.left = (50 + Math.sin(u * 6) * 2) + '%';
        ball.style.transform = 'translate(-50%,-50%) scale(' + sx + ',' + (2 - sx) + ')';
        document.getElementById('introSub').style.opacity = clamp((u - 0.35) * 4);
    }

    function kinetic(u) {
        var idx = Math.min(s.words.length - 1, Math.floor(u * s.words.length));
        var wu = u * s.words.length - idx;
        var p = outExpo(clamp(wu * 1.4));
        var word = document.getElementById('typeword');
        word.textContent = s.words[idx];
        word.style.opacity = clamp(wu * 5) * clamp((1 - wu) * 5);
        word.style.letterSpacing = (-0.06 + 0.03 * p).toFixed(3) + 'em';
        word.style.transform = 'translate(-50%,-50%) translateX(' +
            ((1 - p) * 90).toFixed(2) + 'px) scale(' + (1.16 - 0.16 * p).toFixed(3) + ')';
        document.getElementById('ghostTop').style.transform =
            'translateX(' + (-u * 190).toFixed(1) + 'px)';
        document.getElementById('ghostMid').style.transform =
            'translateX(' + (u * 120).toFixed(1) + 'px)';
        document.getElementById('ghostBottom').style.transform =
            'translateX(' + (-u * 150).toFixed(1) + 'px)';
        for (var i = 0; i < s.beats.length; i++) {
            var phase = u * s.words.length * 8 - i;
            s.beats[i].style.opacity = (0.18 + 0.7 *
                Math.max(0, 1 - Math.abs(phase) * 2)).toFixed(3);
        }
    }

    function systems(u) {
        var i, p, size;
        for (i = 0; i < s.rings.length; i++) {
            p = (u * 1.7 - i * 0.07 + 1) % 1;
            size = 70 + p * 900;
            s.rings[i].style.width = size + 'px';
            s.rings[i].style.height = size + 'px';
            s.rings[i].style.marginLeft = (-size / 2) + 'px';
            s.rings[i].style.marginTop = (-size / 2) + 'px';
            s.rings[i].style.opacity = ((1 - p) * 0.85).toFixed(3);
            s.rings[i].style.transform = 'rotate(' +
                (u * 80 * (i % 2 ? 1 : -1)).toFixed(2) + 'deg)';
        }
        for (i = 0; i < s.crosses.length; i++) {
            var a = i * Math.PI / 8 + u * 0.9;
            var r = 240 + (i % 6) * 78;
            s.crosses[i].style.left = (960 + Math.cos(a) * r - 19) + 'px';
            s.crosses[i].style.top = (540 + Math.sin(a) * r * 0.82 - 19) + 'px';
            s.crosses[i].style.opacity = (0.3 + 0.55 * Math.abs(Math.sin(a * 2))).toFixed(3);
        }
        document.getElementById('sysGrid').style.transform =
            'rotate(' + (u * 6).toFixed(2) + 'deg)';
    }

    function particles(u) {
        var p = outExpo(clamp(u * 1.4));
        for (var i = 0; i < s.glyph.length; i++) {
            var a = i * 0.31;
            var sx = 960 + Math.cos(a) * (240 + (i % 17) * 42);
            var sy = 540 + Math.sin(a) * (180 + (i % 13) * 36);
            s.glyphDots[i].style.left = (sx + (s.glyph[i][0] - sx) * p).toFixed(1) + 'px';
            s.glyphDots[i].style.top = (sy + (s.glyph[i][1] - sy) * p).toFixed(1) + 'px';
            s.glyphDots[i].style.opacity = clamp(u * 2.5).toFixed(3);
        }
        for (var j = 0; j < s.dots.length; j++) {
            var b = j * 0.52 + u * 4.2;
            var r = 90 + (j % 9) * 26 + 140 * u;
            s.dots[j].style.left = (960 + Math.cos(b) * r * 1.65).toFixed(1) + 'px';
            s.dots[j].style.top = (540 + Math.sin(b) * r * 0.75).toFixed(1) + 'px';
            s.dots[j].style.opacity = clamp(u * 2.5) * 0.7;
        }
    }

    function dimension(u) {
        document.getElementById('floor').style.transform =
            'perspective(900px) rotateX(' + (68 - 5 * u).toFixed(2) + 'deg) translate(' +
            (u * 26).toFixed(1) + 'px,' + (-30 * u).toFixed(1) + 'px)';
        var morph = 0.18 + 0.82 * clamp(u * 1.6);
        for (var i = 0; i < s.sphere.length; i++) {
            var a = i * 0.42 + u * 5;
            var b = i * 0.19 + u * 2;
            var r = 215 + 58 * Math.cos(b);
            var x = 960 + Math.cos(a) * r * 1.7;
            var y = 420 + Math.sin(a) * r * 0.75 * morph + 58 * Math.sin(b);
            var k = 0.6 + 0.4 * (Math.sin(b) + 1) / 2;
            s.sphere[i].style.left = x.toFixed(1) + 'px';
            s.sphere[i].style.top = y.toFixed(1) + 'px';
            s.sphere[i].style.transform = 'scale(' + k.toFixed(3) + ')';
            s.sphere[i].style.opacity = (0.35 + 0.6 * k).toFixed(3);
        }
    }

    function data(u) {
        var apply = outExpo(clamp(u * 2));
        var metricNodes = document.querySelectorAll('.metric b');
        for (var j = 0; j < s.targets.length; j++) {
            metricNodes[j].textContent = String(Math.round(s.targets[j] * apply));
        }
        for (var i = 0; i < s.bars.length; i++) {
            s.bars[i].style.height = (18 + 72 * (0.5 + 0.5 *
                Math.sin(i * 0.9 + u * 5))).toFixed(1) + '%';
        }
        var pct = s.ringTarget * apply;
        document.getElementById('ring').style.background =
            'conic-gradient(var(--blue) 0 ' + pct.toFixed(1) + '%,#E6E8EF ' +
            pct.toFixed(1) + '% 100%)';
        document.querySelector('#ring span').textContent = Math.round(pct) + '%';
        document.getElementById('panel').style.opacity = clamp(u * 3);
        document.getElementById('panel').style.transform =
            'translateY(' + ((1 - apply) * 28).toFixed(1) + 'px)';
    }

    function flow(u) {
        var i, k, d;
        for (i = 0; i < s.ribbons.length; i++) {
            s.ribbons[i].setAttribute('stroke',
                i < 8 ? comp.variables.accent :
                (i < 16 ? comp.variables.blue : comp.variables.muted));
            d = '';
            for (k = 0; k <= 30; k++) {
                var x = k / 30 * 1920;
                var y = 540 + (i - 9.5) * 52
                      + Math.sin(x / (260 + i * 9) + u * 2.3 + i * 0.33) * (95 + (i % 7) * 24)
                      + Math.sin(x / 130 - u * 1.4 + i * 0.7) * (14 + (i % 4) * 8);
                d += (k ? ' L' : 'M') + x.toFixed(0) + ' ' + y.toFixed(1);
            }
            s.ribbons[i].setAttribute('d', d);
            s.ribbons[i].style.opacity = (0.22 + 0.5 *
                Math.abs(Math.sin(u * 3 + i * 0.45))).toFixed(3);
        }
        document.getElementById('flowTop').style.opacity = clamp((u - 0.12) * 3);
        document.getElementById('flowBottom').style.opacity = clamp((u - 0.35) * 3);
    }

    function outro(u) {
        var p = outExpo(clamp(u * 2));
        document.getElementById('lockup').style.transform =
            'translate(-50%,-50%) scale(' + (1.07 - 0.07 * p).toFixed(3) + ')';
        document.getElementById('brandDot').style.transform =
            'scale(' + (1 + 0.5 * Math.max(0, 1 - Math.abs(u - 0.35) * 10)).toFixed(3) + ')';
        document.getElementById('statusLine').style.opacity = clamp((u - 0.3) * 3);
        document.getElementById('outroMeta').style.opacity = clamp((u - 0.42) * 4);
        document.getElementById('outroCaption').style.opacity = clamp((u - 0.55) * 4) * 0.7;
    }

    var draw = {
        ch0: intro, ch1: kinetic, ch2: systems, ch3: particles,
        ch4: dimension, ch5: data, ch6: flow, ch7: outro
    };

    window.seek = function (t) {
        var frame = window.__OMNIFRAME_FRAME__;
        var total = window.__OMNIFRAME_TOTAL_FRAMES__ || 900;
        var fps = window.__OMNIFRAME_FPS__ || 60;
        var sec = Math.floor(t);
        var ff = frame % Math.round(fps);
        document.getElementById('hudTR').textContent =
            '00:00:' + String(sec).padStart(2, '0') + ':' + String(ff).padStart(2, '0');
        document.getElementById('hudBR').textContent =
            String(frame).padStart(3, '0') + ' / ' + total;
        document.getElementById('progressFill').style.width =
            (frame / total * 100).toFixed(2) + '%';

        var active = activeTrack(t);
        for (var i = 0; i < s.chapters.length; i++) {
            s.chapters[i].style.display = 'none';
        }
        if (!active) { return; }
        var n = parseInt(active.id.slice(2), 10);
        document.getElementById(active.id).style.display = 'block';
        document.getElementById('hudBL').textContent =
            String(n).padStart(2, '0') + ' — ' + s.chapterNames[n];
        draw[active.id](active.u);
    };

    window.seek(__OMNIFRAME_FRAME__ / __OMNIFRAME_FPS__);
})();
