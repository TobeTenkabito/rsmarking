import { WelcomeTemplate } from '../../../ui/src/templates/Welcome.js';

export const WelcomeModule = {
    canvas: null,
    ctx: null,
    particles: [],
    earthNodes: [],
    animationId: null,
    mouse: { x: -1000, y: -1000, radius: 180 },
    settings: {
        particleCount: 0,
        connectionDistance: 110,
        baseSpeed: 0.6,
        aggrActive: false
    },

    // 赛博多态配色 (Cyan, Purple, Emerald)
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
        this.createEarth(); // 初始化高精度点阵地球
        this.createParticles();

        this.animate = this.animate.bind(this);
        this.animate();

        this.handleMouseMove = this.handleMouseMove.bind(this);
        this.handleMouseOut = this.handleMouseOut.bind(this);
        window.addEventListener('mousemove', this.handleMouseMove);
        window.addEventListener('mouseout', this.handleMouseOut);

        btn.addEventListener('click', () => this.enter(screen));
        window.addEventListener('resize', () => {
            this.resize();
            this.createEarth();
            this.createParticles();
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

    // 核心升级：基于 ASCII 拓扑的高精度世界地图点阵生成
    createEarth() {
        this.earthNodes = [];
        // 100x36 的世界地图拓扑矩阵
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
            "             ################                 #######    ####  ###############################   #  ",
            "               ##########  ##               ####          ###################################  ##   ",
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
                    // 每个陆地区块生成 3 个随机微小偏移的点，增加点云的质感和密度
                    for (let k = 0; k < 3; k++) {
                        const u = (i + Math.random()) / cols;
                        const v = (j + Math.random()) / rows;

                        const lon = (u - 0.5) * Math.PI * 2;
                        const lat = (v - 0.5) * Math.PI;

                        // 底层地图主色调为翠绿(Emerald)，混入 20% 的青色(Cyan)与顶层粒子呼应
                        const color = Math.random() > 0.8 ? [34, 211, 238] : [16, 185, 129];

                        this.earthNodes.push({ u, v, lon, lat, color });
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

        // ==========================================
        // 1. 渲染底层：全息数据地球 (2D平面 <-> 3D球体 循环)
        // ==========================================
        if (!this.settings.aggrActive) {
            const cycleTime = 20000; // 20秒完整循环
            const cycle = (Date.now() % cycleTime) / cycleTime;

            let foldProgress = 0;
            let panOffset = 0;

            if (cycle < 0.25) {
                // 0-5s: 平面地图移动一周
                foldProgress = 0;
                panOffset = cycle * 4;
            } else if (cycle < 0.4) {
                // 5-8s: 平面收拢为 3D 球体
                let t = (cycle - 0.25) / 0.15;
                foldProgress = 0.5 - Math.cos(t * Math.PI) / 2;
                panOffset = 0;
            } else if (cycle < 0.75) {
                // 8-15s: 3D 球体旋转一周
                foldProgress = 1;
                panOffset = (cycle - 0.4) / 0.35;
            } else if (cycle < 0.9) {
                // 15-18s: 3D 球体展开为平面
                let t = (cycle - 0.75) / 0.15;
                foldProgress = 1 - (0.5 - Math.cos(t * Math.PI) / 2);
                panOffset = 0;
            } else {
                // 18-20s: 平面静止展示
                foldProgress = 0;
                panOffset = 0;
            }

            const mapWidth = this.canvas.width * 0.7;
            const mapHeight = mapWidth / 2;
            const radius = mapHeight * 0.7;
            const focalLength = 800;

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

                let alpha = 0.6;
                // 3D 模式下的背面剔除与透明度衰减
                if (foldProgress > 0.5 && z > 0) {
                    alpha = 0.08;
                }

                this.ctx.beginPath();
                this.ctx.arc(screenX, screenY, 1.2 * scale, 0, Math.PI * 2);
                this.ctx.fillStyle = `rgba(${node.color[0]}, ${node.color[1]}, ${node.color[2]}, ${alpha})`;
                this.ctx.fill();
            }
        }

        // ==========================================
        // 2. 渲染顶层：交互式粒子与神经网络连线
        // ==========================================
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
            this.ctx.lineWidth = 0.8;
            for (let i = 0; i < this.particles.length; i++) {
                for (let j = i + 1; j < this.particles.length; j++) {
                    const p1 = this.particles[i];
                    const p2 = this.particles[j];
                    const dx = p1.x - p2.x;
                    const dy = p1.y - p2.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);

                    if (dist < this.settings.connectionDistance) {
                        const opacity = 1 - (dist / this.settings.connectionDistance);

                        const distToMouse1 = Math.sqrt(Math.pow(mx - p1.x, 2) + Math.pow(my - p1.y, 2));
                        const distToMouse2 = Math.sqrt(Math.pow(mx - p2.x, 2) + Math.pow(my - p2.y, 2));

                        let strokeColor = `rgba(${p1.baseColor[0]}, ${p1.baseColor[1]}, ${p1.baseColor[2]}, ${opacity * 0.15})`;

                        if (distToMouse1 < mouseRadius && distToMouse2 < mouseRadius) {
                            strokeColor = `rgba(${p1.baseColor[0]}, ${p1.baseColor[1]}, ${p1.baseColor[2]}, ${opacity * 0.8})`;
                        }

                        this.ctx.beginPath();
                        this.ctx.moveTo(p1.x, p1.y);
                        this.ctx.lineTo(p2.x, p2.y);
                        this.ctx.strokeStyle = strokeColor;
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
