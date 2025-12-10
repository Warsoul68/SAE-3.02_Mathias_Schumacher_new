CREATE TABLE TableRoutage(
   id INT,
   destination VARCHAR(50),
   ville VARCHAR(50),
   InterfaceReseau VARCHAR(50),
   ruleId INT,
   PRIMARY KEY(id)
);

CREATE TABLE InfoCle(
   id INT,
   cle VARCHAR(200),
   PRIMARY KEY(id)
);