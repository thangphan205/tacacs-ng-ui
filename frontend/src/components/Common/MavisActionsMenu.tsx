import { IconButton } from "@chakra-ui/react"
import { BsThreeDotsVertical } from "react-icons/bs"
import type { MavisPublic } from "@/client"
import DeleteMavis from "../Mavises/DeleteMavis"
import EditMavis from "../Mavises/EditMavis"
import { MenuContent, MenuRoot, MenuTrigger } from "../ui/menu"

interface MavisActionsMenuProps {
  mavis: MavisPublic
}

export const MavisActionsMenu = ({ mavis }: MavisActionsMenuProps) => {
  return (
    <MenuRoot>
      <MenuTrigger asChild>
        <IconButton variant="ghost" color="inherit">
          <BsThreeDotsVertical />
        </IconButton>
      </MenuTrigger>
      <MenuContent>
        <EditMavis mavis={mavis} />
        <DeleteMavis mavis={mavis} />
      </MenuContent>
    </MenuRoot>
  )
}
