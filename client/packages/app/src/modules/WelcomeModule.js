import { WelcomeTemplate } from '../../../ui/src/templates/Welcome.js';

const CONNECTION_NEIGHBOR_OFFSETS = [-1, 0, 1];

export const WelcomeModule = {
    canvas: null,
    ctx: null,
    particles: [],
    earthNodes: [],
    animationId: null,
    resizeFrame: null,
    mouse: { x: -1000, y: -1000, radius: 180 },
    settings: {
        particleCount: 0,
        connectionDistance: 110,
        baseSpeed: 0.6,
        aggrActive: false
    },

    // Cyber palette variants (Cyan, Purple, Emerald)
    palette: [
        [34, 211, 238],
        [168, 85, 247],
        [16, 185, 129]
    ],

    init() {
        document.body.insertAdjacentHTML('afterbegin', WelcomeTemplate);

        const screen = document.getElementById('welcome-screen');
        this.canvas = document.getElementById('stardust-canvas');
        this.ctx = this.canvas.getContext('2d', { alpha: false });
        const btn = document.getElementById('btn-enter-system');

        this.resize();
        this.createEarth(); // Initialize high-resolution dotted globe
        this.createParticles();

        this.animate = this.animate.bind(this);
        this.animate();

        this.handleMouseMove = this.handleMouseMove.bind(this);
        this.handleMouseOut = this.handleMouseOut.bind(this);
        window.addEventListener('mousemove', this.handleMouseMove);
        window.addEventListener('mouseout', this.handleMouseOut);

        btn.addEventListener('click', () => this.enter(screen));
        window.addEventListener('resize', () => {
            if (this.resizeFrame) return;
            this.resizeFrame = requestAnimationFrame(() => {
                this.resizeFrame = null;
                this.resize();
                this.createEarth();
                this.createParticles();
            });
        });
    },

    handleMouseMove(e) {
        this.mouse.x = e.clientX;
        this.mouse.y = e.clientY;
    },

    handleMouseOut() {
        this.mouse.x = -1000;
        this.mouse.y = -1000;
    },

    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
        this.settings.particleCount = Math.floor((this.canvas.width * this.canvas.height) / 7000);
    },

    // Generate high-resolution world-map dots from ASCII topology
    createEarth() {
        this.earthNodes = [];
        // 100x36 Englishworld-map topology matrix
        const earthMap = [
            "                                                                                                    ",
            "                                      ######                                                        ",
            "                                    ##########                  ####                                ",
            "     ###################           ###########          ######################################      ",
            "    ######################          #########        ### ########################################   ",
            "    #######################         ########      ####  #########################################   ",
            "      #####################          #####        ###   #########################################   ",
            "        ###################          ###              ############################################# ",
            "          ##################                 ##    ##############################################   ",
            "           ##################                ##   ##############################################    ",
            "            #################                  ################################################ #   ",
            "             ################                 #######    ####   ## ###########################   #  ",
            "               ##########  ##               ####          ######## ##########################  ##   ",
            "                #######                        ########   ###################################   ##  ",
            "                 #####     ####              ################  ##########################  #   ##   ",
            "                   ###      ##             ###################  #########################    ##     ",
            "                    ####                     #################  #########################           ",
            "                     ########                 #################       ##################            ",
            "                     #############                ##########            ##############              ",
            "                      ##############               #########             #######   ###              ",
            "                      ##############               ########               #####     ##              ",
            "                       #############               #######                 ##                       ",
            "                        ###########                ######       ###                     #########   ",
            "                         ########                  #####        ###                   ###########   ",
            "                         ######                    ####         ###                  ############   ",
            "                          ####                      ##                                  ########    ",
            "                          ###                                                              ####     ",
            "                          ##                                                                        ",
            "                          ##                                                                        ",
            "                          #                                                                         ",
            "                            ####                                                                    ",
            "                          #######          ################################                         ",
            "       ################################################################################             ",
            "  ##########################################################################################        ",
            ]

        const rows = earthMap.length;
        const cols = earthMap[0].length;

        for (let j = 0; j < rows; j++) {
        for (let i = 0; i < cols; i++) {
            if (earthMap[j][i] !== ' ') {
                for (let k = 0; k < 3; k++) {
                    // Optimization 1：add slight jitter to reduce grid regularity
                    const jitterX = Math.random() - 0.5;
                    const jitterY = Math.random() - 0.5;
                    const u = (i + 0.5 + jitterX) / cols;
                    const v = (j + 0.5 + jitterY) / rows;

                    const lon = (u - 0.5) * Math.PI * 2;
                    // keep linear mapping for renderer compatibility and add tiny offsets to avoid overlap
                    const lat = (v - 0.5) * Math.PI;

                    // Optimization 2：more refined color logic
                    // weight brightness by latitude for an aurora-like feel
                    const brightness = 0.7 + Math.abs(Math.sin(lat)) * 0.3;
                    const rand = Math.random();
                    let baseColor = rand > 0.9 ? [34, 211, 238] : [16, 185, 129]; // Cyan vs Emerald
                    if (rand < 0.05) baseColor = [168, 85, 247]; // rare purple accent dots

                    const color = baseColor.map(c => Math.floor(c * brightness));

                    // Optimization 3：add varied sizes and phases
                    const size = 0.6 + Math.random() * 0.8;
                    const phase = Math.random() * Math.PI * 2; // for later animation

                    this.earthNodes.push({ u, v, lon, lat, color, size, phase });
                }
            }
        }
    }
    },

    createParticles() {
        this.particles = [];
        for (let i = 0; i < this.settings.particleCount; i++) {
            const color = this.palette[Math.floor(Math.random() * this.palette.length)];
            this.particles.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                vx: (Math.random() - 0.5) * this.settings.baseSpeed,
                vy: (Math.random() - 0.5) * this.settings.baseSpeed,
                size: Math.random() * 8 + 0.5,
                baseColor: color
            });
        }
    },

    animate() {
        if (!this.canvas || !document.getElementById('stardust-canvas')) return;
        this.animationId = requestAnimationFrame(this.animate);

        this.ctx.fillStyle = 'rgba(3, 7, 18, 0.4)';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        const centerX = this.canvas.width / 2;
        const centerY = this.canvas.height / 2;

        if (!this.settings.aggrActive) {
            const now = Date.now();
            const cycleTime = 20000; // 20second full cycle
            const cycle = (now % cycleTime) / cycleTime;

            let foldProgress = 0;
            let panOffset = 0;

            if (cycle < 0.25) {
                // 0-5s: flat map pans once
                foldProgress = 0;
                panOffset = cycle * 4;
            } else if (cycle < 0.4) {
                // 5-8s: flat map folds into 3D globe
                let t = (cycle - 0.25) / 0.15;
                foldProgress = 0.5 - Math.cos(t * Math.PI) / 2;
                panOffset = 0;
            } else if (cycle < 0.75) {
                // 8-15s: 3D globe rotates once
                foldProgress = 1;
                panOffset = (cycle - 0.4) / 0.35;
            } else if (cycle < 0.9) {
                // 15-18s: 3D globe unfolds into flat map
                let t = (cycle - 0.75) / 0.15;
                foldProgress = 1 - (0.5 - Math.cos(t * Math.PI) / 2);
                panOffset = 0;
            } else {
                // 18-20s: flat map remains still
                foldProgress = 0;
                panOffset = 0;
            }

            const mapWidth = this.canvas.width * 0.7;
            const mapHeight = mapWidth / 2;
            const radius = mapHeight * 0.7;
            const focalLength = 800;

            const time = now;

            for (let i = 0; i < this.earthNodes.length; i++) {
                const node = this.earthNodes[i];
                let currentU = (node.u + panOffset) % 1;
                let currentLon = (currentU - 0.5) * Math.PI * 2;
                const flatX = (currentU - 0.5) * mapWidth;
                const flatY = (node.v - 0.5) * mapHeight;
                const flatZ = 0;
                const sphereX = radius * Math.cos(node.lat) * Math.sin(currentLon);
                const sphereY = radius * Math.sin(node.lat);
                const sphereZ = radius * Math.cos(node.lat) * Math.cos(currentLon);
                const x = flatX * (1 - foldProgress) + sphereX * foldProgress;
                const y = flatY * (1 - foldProgress) + sphereY * foldProgress;
                const z = flatZ * (1 - foldProgress) + sphereZ * foldProgress;
                const scale = focalLength / (focalLength + z + radius * foldProgress);
                const screenX = centerX + x * scale;
                const screenY = centerY + y * scale;
                let depthAlpha = 0.6;
                if (foldProgress > 0.1) {
                    const normalizedZ = (radius - z) / (2 * radius);
                    depthAlpha = z < 0 ? 0.2 + normalizedZ * 0.6 : 0.05 + normalizedZ * 0.1;
                }
                const breath = Math.sin(time * 0.002 + i * 0.5) * 0.2 + 0.8;
                const finalAlpha = depthAlpha * breath;
                const dotSize = (node.size || 1.2) * scale * (z < 0 ? 1.0 : 0.7);
                this.ctx.beginPath();
                this.ctx.arc(screenX, screenY, dotSize, 0, Math.PI * 2);
                let r = node.color[0], g = node.color[1], b = node.color[2];
                if (z > 0 && foldProgress > 0.5) {
                    b = Math.min(255, b + 50);
                }
                this.ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${finalAlpha})`;
                this.ctx.fill();
                if (z < -radius * 0.8 && Math.random() > 0.9995) {
                    this.ctx.shadowBlur = 10;
                    this.ctx.shadowColor = `rgba(255, 255, 255, 0.8)`;
                    this.ctx.fillStyle = "#fff";
                    this.ctx.fill();
                    this.ctx.shadowBlur = 0;
                }
            }
        }

        const { x: mx, y: my, radius: mouseRadius } = this.mouse;

        for (let i = 0; i < this.particles.length; i++) {
            const p = this.particles[i];

            if (this.settings.aggrActive) {
                p.x += p.vx;
                p.y += p.vy;
            } else {
                let dx = mx - p.x;
                let dy = my - p.y;
                let distance = Math.sqrt(dx * dx + dy * dy);

                if (distance < mouseRadius) {
                    const forceDirectionX = dx / distance;
                    const forceDirectionY = dy / distance;
                    const force = (mouseRadius - distance) / mouseRadius;

                    p.vx -= forceDirectionX * force * 0.6;
                    p.vy -= forceDirectionY * force * 0.6;
                }

                const speed = Math.sqrt(p.vx * p.vx + p.vy * p.vy);
                if (speed > 3) {
                    p.vx = (p.vx / speed) * 3;
                    p.vy = (p.vy / speed) * 3;
                }

                if (speed < this.settings.baseSpeed) {
                    p.vx *= 1.01;
                    p.vy *= 1.01;
                }

                p.x += p.vx;
                p.y += p.vy;

                if (p.x < 0 || p.x > this.canvas.width) p.vx *= -1;
                if (p.y < 0 || p.y > this.canvas.height) p.vy *= -1;
            }

            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);

            let distToMouse = Math.sqrt(Math.pow(mx - p.x, 2) + Math.pow(my - p.y, 2));
            let alpha = distToMouse < mouseRadius ? 0.9 : 0.3;

            this.ctx.fillStyle = `rgba(${p.baseColor[0]}, ${p.baseColor[1]}, ${p.baseColor[2]}, ${alpha})`;
            this.ctx.fill();
        }

        if (!this.settings.aggrActive) {
            this.drawParticleConnections(mx, my, mouseRadius);
        }
    },

    drawParticleConnections(mx, my, mouseRadius) {
        const distance = this.settings.connectionDistance;
        const distanceSq = distance * distance;
        const mouseRadiusSq = mouseRadius * mouseRadius;
        const grid = new Map();

        for (let i = 0; i < this.particles.length; i++) {
            const p = this.particles[i];
            const cx = Math.floor(p.x / distance);
            const cy = Math.floor(p.y / distance);
            const key = `${cx}:${cy}`;
            let bucket = grid.get(key);
            if (!bucket) {
                bucket = [];
                grid.set(key, bucket);
            }
            bucket.push(i);
        }

        this.ctx.lineWidth = 0.8;
        for (let i = 0; i < this.particles.length; i++) {
            const p1 = this.particles[i];
            const cx = Math.floor(p1.x / distance);
            const cy = Math.floor(p1.y / distance);

            for (const ox of CONNECTION_NEIGHBOR_OFFSETS) {
                for (const oy of CONNECTION_NEIGHBOR_OFFSETS) {
                    const bucket = grid.get(`${cx + ox}:${cy + oy}`);
                    if (!bucket) continue;

                    for (const j of bucket) {
                        if (j <= i) continue;
                        const p2 = this.particles[j];
                        const dx = p1.x - p2.x;
                        const dy = p1.y - p2.y;
                        const distSq = dx * dx + dy * dy;
                        if (distSq >= distanceSq) continue;

                        const dist = Math.sqrt(distSq);
                        const opacity = 1 - (dist / distance);
                        const mouseDx1 = mx - p1.x;
                        const mouseDy1 = my - p1.y;
                        const mouseDx2 = mx - p2.x;
                        const mouseDy2 = my - p2.y;
                        const nearMouse = (
                            mouseDx1 * mouseDx1 + mouseDy1 * mouseDy1 < mouseRadiusSq &&
                            mouseDx2 * mouseDx2 + mouseDy2 * mouseDy2 < mouseRadiusSq
                        );
                        const alpha = nearMouse ? opacity * 0.8 : opacity * 0.15;

                        this.ctx.beginPath();
                        this.ctx.moveTo(p1.x, p1.y);
                        this.ctx.lineTo(p2.x, p2.y);
                        this.ctx.strokeStyle = `rgba(${p1.baseColor[0]}, ${p1.baseColor[1]}, ${p1.baseColor[2]}, ${alpha})`;
                        this.ctx.stroke();
                    }
                }
            }
        }
    },

    enter(el) {
        this.settings.aggrActive = true;

        const logo = document.getElementById('aggr-logo');
        if (logo) {
            logo.style.transform = 'scale(2) translateZ(0)';
            logo.style.filter = 'blur(15px) brightness(2)';
            logo.style.opacity = '0';
        }

        const centerX = this.canvas.width / 2;
        const centerY = this.canvas.height / 2;
        this.particles.forEach(p => {
            const angle = Math.atan2(p.y - centerY, p.x - centerX);
            const force = Math.random() * 20 + 10;
            p.vx = Math.cos(angle) * force;
            p.vy = Math.sin(angle) * force;
        });

        setTimeout(() => {
            el.classList.add('exit-active');
            setTimeout(() => {
                cancelAnimationFrame(this.animationId);
                window.removeEventListener('mousemove', this.handleMouseMove);
                window.removeEventListener('mouseout', this.handleMouseOut);
                el.remove();
                this.canvas = null;
            }, 1500);
        }, 300);
    }
};
