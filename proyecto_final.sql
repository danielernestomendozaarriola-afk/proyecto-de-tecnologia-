create database if not exists control_gastos_personales;
use control_gastos_personales;

create table if not exists usuarios (
    id_usuario int auto_increment primary key,
    nombre varchar(100) not null,
    correo varchar(100) not null unique,
    usuario varchar(50) not null unique,
    password_hash varchar(255) not null,
    descripcion varchar(255) default 'Estudiante de desarrollo de software. Me gusta aprender sobre tecnología, diseño y programación.',
    foto mediumtext
);

create table if not exists ingresos (
    id_ingreso int auto_increment primary key,
    id_usuario int not null,
    cantidad decimal(10,2) not null,
    fecha date not null,
    descripcion varchar(100),
    foreign key (id_usuario) references usuarios(id_usuario) on delete cascade
);

create table if not exists gastos (
    id_gasto int auto_increment primary key,
    id_usuario int not null,
    nombre_gasto varchar(100) not null,
    categoria enum('alimentacion', 'transporte', 'educacion', 'entretenimiento', 'otros') not null,
    cantidad decimal(10,2) not null,
    fecha date not null,
    foreign key (id_usuario) references usuarios(id_usuario) on delete cascade
);

-- Nueva: meta de ahorro (la pantalla "Panel" la usa)
create table if not exists metas (
    id_usuario int primary key,
    nombre varchar(100) not null,
    monto_meta decimal(10,2) not null,
    foreign key (id_usuario) references usuarios(id_usuario) on delete cascade
);

-- Consultas útiles (cámbialas por el id que quieras probar):
-- select * from gastos where categoria = 'alimentacion';
-- select categoria, sum(cantidad) from gastos where id_usuario = 1 group by categoria;
