/**
 * login-misbah.js – ثلوج متساقطة + إضاءة البطاقة عند المرور
 */
(function () {
  'use strict';

  var canvas = document.getElementById('snowCanvas');
  if (!canvas) return;

  var ctx = canvas.getContext('2d');
  var snowflakes = [];

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }

  function initSnow() {
    snowflakes.length = 0;
    for (var i = 0; i < 200; i++) {
      snowflakes.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        radius: Math.random() * 3 + 1,
        speed: Math.random() * 1 + 0.5
      });
    }
  }

  function moveSnow() {
    var i, flake;
    for (i = 0; i < snowflakes.length; i++) {
      flake = snowflakes[i];
      flake.y += flake.speed;
      if (flake.y > canvas.height) {
        flake.y = 0;
        flake.x = Math.random() * canvas.width;
      }
    }
  }

  function drawSnow() {
    if (!ctx || !canvas.width || !canvas.height) {
      requestAnimationFrame(drawSnow);
      return;
    }
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = 'white';
    ctx.beginPath();
    for (var i = 0; i < snowflakes.length; i++) {
      var f = snowflakes[i];
      ctx.moveTo(f.x, f.y);
      ctx.arc(f.x, f.y, f.radius, 0, Math.PI * 2);
    }
    ctx.fill();
    moveSnow();
    requestAnimationFrame(drawSnow);
  }

  resize();
  initSnow();
  drawSnow();

  window.addEventListener('resize', function () {
    resize();
    initSnow();
  });

  /* إضاءة متقدمة عند المرور على البطاقة */
  var card = document.querySelector('.login-card');
  if (card) {
    card.addEventListener('mousemove', function (e) {
      var rect = card.getBoundingClientRect();
      var x = e.clientX - rect.left;
      var y = e.clientY - rect.top;
      card.style.boxShadow = '0 0 50px rgba(255,255,255,0.5) ' + (x / 10) + 'px ' + (y / 10) + 'px';
    });
    card.addEventListener('mouseleave', function () {
      card.style.boxShadow = '0 0 30px rgba(255, 255, 255, 0.2)';
    });
  }
})();
